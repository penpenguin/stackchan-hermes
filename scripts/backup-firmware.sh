#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --port /dev/... --output-dir DIR --boot-log FILE --firmware-version VERSION --partition-offset HEX --partition-size HEX [--execute-read]" >&2
}

serial_port=""
output_dir=""
boot_log=""
firmware_version=""
partition_offset=""
partition_size=""
execute_read=false
while (($#)); do
  case "$1" in
    --port)
      serial_port="${2:-}"
      shift 2
      ;;
    --output-dir)
      output_dir="${2:-}"
      shift 2
      ;;
    --boot-log)
      boot_log="${2:-}"
      shift 2
      ;;
    --firmware-version)
      firmware_version="${2:-}"
      shift 2
      ;;
    --partition-offset)
      partition_offset="${2:-}"
      shift 2
      ;;
    --partition-size)
      partition_size="${2:-}"
      shift 2
      ;;
    --execute-read)
      execute_read=true
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$serial_port" || -z "$output_dir" || -z "$boot_log" || -z "$firmware_version" || -z "$partition_offset" || -z "$partition_size" ]]; then
  usage
  exit 2
fi
if [[ "$serial_port" != /dev/* ]]; then
  echo "refusing backup: --port must be an explicit /dev path" >&2
  exit 2
fi
if [[ ! "$partition_offset" =~ ^0x[0-9A-Fa-f]+$ || ! "$partition_size" =~ ^0x[0-9A-Fa-f]+$ ]]; then
  echo "refusing backup: verified partition offset and size must be hexadecimal" >&2
  exit 2
fi
if [[ "$execute_read" != true ]]; then
  echo "DRY RUN: no serial access or output write was performed."
  echo "factory: 16 verified 0x100000-byte reads covering 0x0..0x1000000, up to 3 attempts each, assembled into <factory.bin>"
  echo "factory chunk: esptool.py --chip esp32s3 --port ${serial_port} --before default_reset --after no_reset read_flash <offset> 0x100000 <chunk.bin> --no-progress"
  echo "partition: esptool.py --chip esp32s3 --port ${serial_port} --before default_reset --after hard_reset read_flash ${partition_offset} ${partition_size} <partition-table.bin>"
  echo "Re-run with --execute-read only after verifying the hardware, stable serial ID, partition values, boot log, and destination."
  exit 0
fi
if [[ ! -c "$serial_port" ]]; then
  echo "refusing backup: --port must identify one existing serial character device" >&2
  exit 2
fi
if [[ ! -f "$boot_log" || -L "$boot_log" ]]; then
  echo "refusing backup: a regular pre-flash boot log is required" >&2
  exit 2
fi
if ! command -v esptool.py >/dev/null 2>&1; then
  echo "missing required command: esptool.py" >&2
  exit 2
fi
if ! command -v shasum >/dev/null 2>&1; then
  echo "missing required command: shasum" >&2
  exit 2
fi

mkdir -p "$output_dir"
chmod 700 "$output_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
factory_name="factory-${timestamp}.bin"
factory_partial="${output_dir}/.${factory_name}.partial"
factory_chunk="${output_dir}/.${factory_name}.chunk.partial"
factory_image="${output_dir}/${factory_name}"
partition_image="${output_dir}/partition-table.bin"
metadata_file="${output_dir}/factory-${timestamp}.metadata.txt"

if [[ -e "$factory_image" || -e "$partition_image" || -e "$metadata_file" ]]; then
  echo "refusing backup: output artifacts already exist" >&2
  exit 2
fi

cleanup() {
  rm -f -- "$factory_partial" "$factory_chunk"
}
trap cleanup EXIT

factory_chunk_size=$((0x100000))
factory_chunk_count=16
factory_chunk_attempts=3
: > "$factory_partial"
for ((chunk_index = 0; chunk_index < factory_chunk_count; chunk_index++)); do
  chunk_offset_decimal=$((chunk_index * factory_chunk_size))
  printf -v chunk_offset '0x%x' "$chunk_offset_decimal"
  chunk_read=false
  for ((attempt = 1; attempt <= factory_chunk_attempts; attempt++)); do
    rm -f -- "$factory_chunk"
    if esptool.py --chip esp32s3 --port "$serial_port" \
      --before default_reset --after no_reset \
      read_flash "$chunk_offset" 0x100000 "$factory_chunk" --no-progress; then
      chunk_size="$(wc -c < "$factory_chunk" | tr -d '[:space:]')"
      if [[ "$chunk_size" == "1048576" ]]; then
        chunk_read=true
        break
      fi
      echo "factory chunk size mismatch at ${chunk_offset}: expected 1048576, got ${chunk_size}" >&2
    fi
    echo "retrying factory chunk ${chunk_offset} after failed attempt ${attempt}/${factory_chunk_attempts}" >&2
  done
  if [[ "$chunk_read" != true ]]; then
    echo "factory chunk read failed at ${chunk_offset} after ${factory_chunk_attempts} attempts" >&2
    exit 1
  fi
  dd if="$factory_chunk" of="$factory_partial" bs="$factory_chunk_size" \
    seek="$chunk_index" conv=notrunc status=none
  rm -f -- "$factory_chunk"
done
factory_size="$(wc -c < "$factory_partial" | tr -d '[:space:]')"
if [[ "$factory_size" != "16777216" ]]; then
  echo "factory backup size mismatch: expected 16777216, got ${factory_size}" >&2
  exit 1
fi
mv -- "$factory_partial" "$factory_image"
esptool.py --chip esp32s3 --port "$serial_port" --before default_reset --after hard_reset \
  read_flash "$partition_offset" "$partition_size" "$partition_image"

(
  cd "$output_dir"
  shasum -a 256 "$factory_name" > "${factory_name}.sha256"
  shasum -a 256 "partition-table.bin" > "partition-table.bin.sha256"
)
cp -- "$boot_log" "${output_dir}/factory-${timestamp}.boot.log"
chmod 600 "$factory_image" "$partition_image" "${output_dir}"/*.sha256 \
  "${output_dir}/factory-${timestamp}.boot.log"

{
  echo "serial_port=${serial_port}"
  echo "firmware_version=${firmware_version}"
  echo "factory_size_bytes=${factory_size}"
  echo "created_at_utc=${timestamp}"
  echo "partition_offset=${partition_offset}"
  echo "partition_size=${partition_size}"
  echo "restore_requires_explicit_review=true"
  echo "restore_command=esptool.py --chip esp32s3 --port <REVIEWED_SERIAL_PORT> write_flash 0x0 ${factory_name}"
} > "$metadata_file"
chmod 600 "$metadata_file"

echo "verified factory backup: ${factory_image}"
echo "No flash or restore command was executed; the reviewed restore command is in ${metadata_file}."
