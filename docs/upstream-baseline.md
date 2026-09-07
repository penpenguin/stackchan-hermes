# Upstream baseline investigation

調査日: 2026-08-28（Asia/Tokyo）

この文書の表と調査結果は Phase 0 時点の read-only snapshot です。SHA は調査時点の default
branch `HEAD`。その後、公式 StackChan の固定 commit はライセンス確認済み vendor snapshot
として取り込まれ、project-owned component/HAL overlay として統合されました。現在の正規な
来歴と差分は `firmware/UPSTREAM.md` と `firmware/upstream-lock.json` を参照してください。

## Pinned references

| Repository | Branch | Commit | Commit date | Finding |
| --- | --- | --- | --- | --- |
| [`m5stack/StackChan`](https://github.com/m5stack/StackChan) | `main` | `1b5765599fba8aaad1811d9a79358ccc7051f5f3` | 2026-08-19 | Official CoreS3 firmware baseline; project version `1.5.1` |
| [`m5stack/StackChan-BSP`](https://github.com/m5stack/StackChan-BSP) | `main` | `621602709d8206edfbf032539dddc6506363836a` | 2026-08-28 | Official BSP reference |
| [`kisaragi-mochi/stackchan-mcp`](https://github.com/kisaragi-mochi/stackchan-mcp) | `main` | `558cf404dcd215993d5af9a4495fd34339b6c314` | 2026-08-23 | Python gateway/MCP, reconnect, audio, packaging reference |
| [`circlemouth/Hermes-StackChan`](https://github.com/circlemouth/Hermes-StackChan) | `main` | `66f03b734fb7434283a79f5409761993751a7676` | 2026-07-10 | CoreS3/Hermes integration and physical failure reference |
| [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) | `main` | `4e7eb39947f132f961923f9e3f600bc8e63066dd` | 2026-08-27 | Public Responses API and MCP host reference |

## Official firmware toolchain

`m5stack/StackChan/firmware/README.md` pins **ESP-IDF v5.5.4** and documents:

```bash
python3 ./fetch_repos.py
idf.py build
```

The official firmware manifest requires ESP-IDF `>=5.5.2`; this project pins the stricter
documented version `v5.5.4`. Its `repos.json` currently pulls, among others, xiaozhi-esp32
`v2.2.4`, ArduinoJson `v7.4.2`, and fixed UI component tags. Those transitive references
must be re-recorded when the baseline is actually imported.

## License findings

- Official `m5stack/StackChan/firmware` is MIT at the pinned SHA.
- Its currently vendored `FTServo_Arduino` directory has an MIT license. This is materially
  different from older/reference trees that contain GPL-3.0 SCServo files.
- `m5stack/StackChan-BSP` is MIT.
- `stackchan-mcp` declares its gateway/repository MIT, but documents GPL-3.0 for an optional
  legacy SCServo implementation. No source is copied from it.
- `circlemouth/Hermes-StackChan` has an MIT `firmware/LICENSE`, but no top-level license was
  found for the complete repository or `ai-server`. Treat it as behavioral reference only.
- HermesAgent is MIT.

Before any code copy, verify the exact source file and its history rather than relying only
on a repository-level label.

## Hardware-specific evidence to preserve

The reference integrations report that CoreS3 LCD and SD access share SPI/GPIO resources and
that serial-bus servo handling is safety-sensitive. These findings influence the future safety
design, but reference code has not been copied. Exact GPIO, LCD reset order, servo limits, and
SD behavior must be verified against the pinned official source and the connected K151 hardware
before implementation or flash.

## Revalidation rule

Do not silently move these SHAs. An upstream update requires:

1. a dedicated ADR or ADR amendment;
2. license diff and dependency diff;
3. host tests and `idf.py build` on the candidate SHA;
4. review of partition table, board config, servo driver, audio, camera, and provisioning changes;
5. an updated `firmware/UPSTREAM.md` and this document.
