# Define xiaozhi source directory
set(XIAOZHI_MAIN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../xiaozhi-esp32/main")

file(GLOB_RECURSE STACK_CHAN_SOURCES CONFIGURE_DEPENDS
    "apps/*.c"
    "apps/*.cc"
    "apps/*.cpp"
    "assets/*.c"
    "assets/*.cc"
    "assets/*.cpp"
    "hal/*.c"
    "hal/*.cc"
    "hal/*.cpp"
    "stackchan/*.c"
    "stackchan/*.cc"
    "stackchan/*.cpp"
)
set(STACK_CHAN_INCLUDE_DIRS 
    "."
)
list(APPEND STACK_CHAN_SOURCES main.cpp)

# Shared local-only upstream implementation. Legacy cloud units are never compiled.
set(SOURCES
    "audio/audio_codec.cc"
    "audio/audio_service.cc"
    "audio/demuxer/ogg_demuxer.cc"
    "display/display.cc"
    "display/lvgl_display/lvgl_display.cc"
    "display/lvgl_display/emoji_collection.cc"
    "display/lvgl_display/lvgl_theme.cc"
    "display/lvgl_display/lvgl_font.cc"
    "display/lvgl_display/lvgl_image.cc"
    "display/lvgl_display/gif/lvgl_gif.cc"
    "display/lvgl_display/gif/gifdec.c"
    "display/lvgl_display/jpg/image_to_jpeg.cpp"
    "display/lvgl_display/jpg/jpeg_to_image.c"
    "system_info.cc"
    "settings.cc"
    "assets.cc"
)

# Transform relative paths to absolute paths from xiaozhi-esp32/main
list(TRANSFORM SOURCES PREPEND "${XIAOZHI_MAIN_DIR}/")

set(INCLUDE_DIRS "." "display" "display/lvgl_display" "display/lvgl_display/jpg" "audio" "audio/demuxer")
# Transform include dirs to absolute paths from xiaozhi-esp32/main
list(TRANSFORM INCLUDE_DIRS PREPEND "${XIAOZHI_MAIN_DIR}/")

# Shared CoreS3 hardware and local Wi-Fi provisioning.
list(APPEND SOURCES
    "${XIAOZHI_MAIN_DIR}/boards/common/board.cc"
    "${XIAOZHI_MAIN_DIR}/boards/common/wifi_board.cc"
    "${XIAOZHI_MAIN_DIR}/boards/common/axp2101.cc"
    "${XIAOZHI_MAIN_DIR}/boards/common/backlight.cc"
    "${XIAOZHI_MAIN_DIR}/boards/common/i2c_device.cc"
    ${STACK_CHAN_SOURCES}
)
list(APPEND INCLUDE_DIRS ${XIAOZHI_MAIN_DIR}/boards/common ${STACK_CHAN_INCLUDE_DIRS})


idf_build_get_property(build_components BUILD_COMPONENTS)
# Function to find component dynamically by pattern
function(find_component_by_pattern PATTERN COMPONENT_VAR PATH_VAR)
    foreach(COMPONENT ${build_components})
        if(COMPONENT MATCHES "${PATTERN}")
            set(${COMPONENT_VAR} ${COMPONENT} PARENT_SCOPE)
            idf_component_get_property(COMPONENT_PATH ${COMPONENT} COMPONENT_DIR)
            set(${PATH_VAR} "${COMPONENT_PATH}" PARENT_SCOPE)
            break()
        endif()
    endforeach()
endfunction()

# Set default BUILTIN_TEXT_FONT and BUILTIN_ICON_FONT
set(BUILTIN_TEXT_FONT font_stackchan_basic_20_4)
set(BUILTIN_ICON_FONT font_awesome_20_4)

set(EMOTE_RESOLUTION "320_240")

# Add board files according to BOARD_TYPE
# Set default assets if the board uses partition table V2
if(CONFIG_BOARD_TYPE_M5STACK_STACK_CHAN)
    set(BOARD_TYPE "m5stack-stack-chan")
    set(BUILTIN_TEXT_FONT font_stackchan_basic_20_4)
    set(BUILTIN_ICON_FONT font_awesome_20_4)
    set(DEFAULT_EMOJI_COLLECTION twemoji_64)
endif()


# Select audio processor according to Kconfig
if(CONFIG_USE_AUDIO_PROCESSOR)
    list(APPEND SOURCES "${XIAOZHI_MAIN_DIR}/audio/processors/afe_audio_processor.cc")
else()
    list(APPEND SOURCES "${XIAOZHI_MAIN_DIR}/audio/processors/no_audio_processor.cc")
endif()
if(CONFIG_IDF_TARGET_ESP32S3 OR CONFIG_IDF_TARGET_ESP32P4)
    list(APPEND SOURCES "${XIAOZHI_MAIN_DIR}/audio/wake_words/afe_wake_word.cc")
    list(APPEND SOURCES "${XIAOZHI_MAIN_DIR}/audio/wake_words/custom_wake_word.cc")
else()
    list(APPEND SOURCES "${XIAOZHI_MAIN_DIR}/audio/wake_words/esp_wake_word.cc")
endif()

# Select language directory according to Kconfig
if(CONFIG_LANGUAGE_ZH_CN)
    set(LANG_DIR "zh-CN")
elseif(CONFIG_LANGUAGE_ZH_TW)
    set(LANG_DIR "zh-TW")
elseif(CONFIG_LANGUAGE_EN_US)
    set(LANG_DIR "en-US")
elseif(CONFIG_LANGUAGE_JA_JP)
    set(LANG_DIR "ja-JP")
elseif(CONFIG_LANGUAGE_KO_KR)
    set(LANG_DIR "ko-KR")
elseif(CONFIG_LANGUAGE_VI_VN)
    set(LANG_DIR "vi-VN")
elseif(CONFIG_LANGUAGE_TH_TH)
    set(LANG_DIR "th-TH")
elseif(CONFIG_LANGUAGE_DE_DE)
    set(LANG_DIR "de-DE")
elseif(CONFIG_LANGUAGE_FR_FR)
    set(LANG_DIR "fr-FR")
elseif(CONFIG_LANGUAGE_ES_ES)
    set(LANG_DIR "es-ES")
elseif(CONFIG_LANGUAGE_IT_IT)
    set(LANG_DIR "it-IT")
elseif(CONFIG_LANGUAGE_RU_RU)
    set(LANG_DIR "ru-RU")
elseif(CONFIG_LANGUAGE_AR_SA)
    set(LANG_DIR "ar-SA")
elseif(CONFIG_LANGUAGE_HI_IN)
    set(LANG_DIR "hi-IN")
elseif(CONFIG_LANGUAGE_PT_PT)
    set(LANG_DIR "pt-PT")
elseif(CONFIG_LANGUAGE_PL_PL)
    set(LANG_DIR "pl-PL")
elseif(CONFIG_LANGUAGE_CS_CZ)
    set(LANG_DIR "cs-CZ")
elseif(CONFIG_LANGUAGE_FI_FI)
    set(LANG_DIR "fi-FI")
elseif(CONFIG_LANGUAGE_TR_TR)
    set(LANG_DIR "tr-TR")
elseif(CONFIG_LANGUAGE_ID_ID)
    set(LANG_DIR "id-ID")
elseif(CONFIG_LANGUAGE_UK_UA)
    set(LANG_DIR "uk-UA")
elseif(CONFIG_LANGUAGE_RO_RO)
    set(LANG_DIR "ro-RO")
elseif(CONFIG_LANGUAGE_BG_BG)
    set(LANG_DIR "bg-BG")
elseif(CONFIG_LANGUAGE_CA_ES)
    set(LANG_DIR "ca-ES")
elseif(CONFIG_LANGUAGE_DA_DK)
    set(LANG_DIR "da-DK")
elseif(CONFIG_LANGUAGE_EL_GR)
    set(LANG_DIR "el-GR")
elseif(CONFIG_LANGUAGE_FA_IR)
    set(LANG_DIR "fa-IR")
elseif(CONFIG_LANGUAGE_FIL_PH)
    set(LANG_DIR "fil-PH")
elseif(CONFIG_LANGUAGE_HE_IL)
    set(LANG_DIR "he-IL")
elseif(CONFIG_LANGUAGE_HR_HR)
    set(LANG_DIR "hr-HR")
elseif(CONFIG_LANGUAGE_HU_HU)
    set(LANG_DIR "hu-HU")
elseif(CONFIG_LANGUAGE_MS_MY)
    set(LANG_DIR "ms-MY")
elseif(CONFIG_LANGUAGE_NB_NO)
    set(LANG_DIR "nb-NO")
elseif(CONFIG_LANGUAGE_NL_NL)
    set(LANG_DIR "nl-NL")
elseif(CONFIG_LANGUAGE_SK_SK)
    set(LANG_DIR "sk-SK")
elseif(CONFIG_LANGUAGE_SL_SI)
    set(LANG_DIR "sl-SI")
elseif(CONFIG_LANGUAGE_SV_SE)
    set(LANG_DIR "sv-SE")
elseif(CONFIG_LANGUAGE_SR_RS)
    set(LANG_DIR "sr-RS")
endif()

# Define generation path
set(LANG_JSON "${XIAOZHI_MAIN_DIR}/assets/locales/${LANG_DIR}/language.json")
set(LANG_HEADER "${XIAOZHI_MAIN_DIR}/assets/lang_config.h")

# Collect current language audio files
file(GLOB LANG_SOUNDS ${XIAOZHI_MAIN_DIR}/assets/locales/${LANG_DIR}/*.ogg)

# If not en-US, collect en-US audio files as fallback for missing files
if(NOT LANG_DIR STREQUAL "en-US")
    file(GLOB EN_US_SOUNDS ${XIAOZHI_MAIN_DIR}/assets/locales/en-US/*.ogg)
    
    # Extract filenames (without path) from current language
    set(EXISTING_NAMES "")
    foreach(SOUND_FILE ${LANG_SOUNDS})
        get_filename_component(FILENAME ${SOUND_FILE} NAME)
        list(APPEND EXISTING_NAMES ${FILENAME})
    endforeach()
    
    # Only add en-US audio files that are missing in current language
    foreach(EN_SOUND ${EN_US_SOUNDS})
        get_filename_component(FILENAME ${EN_SOUND} NAME)
        if(NOT ${FILENAME} IN_LIST EXISTING_NAMES)
            list(APPEND LANG_SOUNDS ${EN_SOUND})
            message(STATUS "Using en-US fallback for missing audio: ${FILENAME}")
        endif()
    endforeach()
endif()

# file(GLOB COMMON_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/common/*.ogg)
file(GLOB COMMON_SOUNDS 
    ${XIAOZHI_MAIN_DIR}/assets/common/*.ogg
    assets/sfx/*.ogg
)

idf_component_register(SRCS ${SOURCES}
                    EMBED_FILES ${LANG_SOUNDS} ${COMMON_SOUNDS}
                    INCLUDE_DIRS ${INCLUDE_DIRS}
                    WHOLE_ARCHIVE
                    PRIV_REQUIRES
                        esp_pm
                        esp_psram
                        esp_netif
                        esp_driver_gpio
                        esp_driver_uart
                        esp_driver_spi
                        esp_driver_i2c
                        esp_driver_i2s
                        esp_driver_jpeg
                        esp_driver_ppa
                        esp_app_format
                        spi_flash
                        console
                        efuse
                        bt
                        fatfs
                        ArduinoJson
                        esp-now
                        mooncake
                        mooncake_log
                        pthread
                        smooth_ui_toolkit
                        stackchan_bridge_client
                        espressif__mdns
                    )

# The pinned esp-now component wraps these SDK log functions. Keep its wrappers
# reachable even when the application has no earlier esp_log_write reference.
target_link_libraries(${COMPONENT_LIB} INTERFACE
    "-Wl,-u,__wrap_esp_log_write"
    "-Wl,-u,__wrap_esp_log_writev"
)

# Replace the OTA settings code/page in the pinned Wi-Fi provisioning component.
# Keep the managed cache intact; verify both sides of the patch on every configure.
find_component_by_pattern("^78__esp-wifi-connect$" WIFI_COMPONENT WIFI_COMPONENT_PATH)
if(NOT WIFI_COMPONENT)
    message(FATAL_ERROR "Pinned Wi-Fi provisioning component was not resolved")
endif()
idf_build_get_property(LOCAL_BUILD_DIR BUILD_DIR)
set(LOCAL_WIFI_DIR "${LOCAL_BUILD_DIR}/local-wifi")
execute_process(
    COMMAND "${PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/../tools/prepare_local_wifi.py" "${LOCAL_WIFI_DIR}"
    RESULT_VARIABLE LOCAL_WIFI_PATCH_RESULT
)
if(NOT LOCAL_WIFI_PATCH_RESULT EQUAL 0)
    message(FATAL_ERROR "Local Wi-Fi patch verification failed")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/../patches/esp-wifi-connect.patch"
    "${CMAKE_CURRENT_SOURCE_DIR}/../patches/esp-wifi-connect.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/../tools/prepare_local_wifi.py"
)
idf_component_get_property(WIFI_LIB ${WIFI_COMPONENT} COMPONENT_LIB)
get_target_property(WIFI_SOURCES ${WIFI_LIB} SOURCES)
set(LOCAL_WIFI_SOURCES "")
set(WIFI_SOURCE_REMOVED FALSE)
set(WIFI_PAGE_REMOVED FALSE)
foreach(WIFI_SOURCE IN LISTS WIFI_SOURCES)
    get_filename_component(WIFI_SOURCE_NAME "${WIFI_SOURCE}" NAME)
    if(WIFI_SOURCE_NAME STREQUAL "wifi_configuration_ap.cc")
        set(WIFI_SOURCE_REMOVED TRUE)
    elseif(WIFI_SOURCE_NAME STREQUAL "wifi_configuration.html.S")
        set(WIFI_PAGE_REMOVED TRUE)
    else()
        list(APPEND LOCAL_WIFI_SOURCES "${WIFI_SOURCE}")
    endif()
endforeach()
if(NOT WIFI_SOURCE_REMOVED OR NOT WIFI_PAGE_REMOVED)
    message(FATAL_ERROR "Pinned Wi-Fi provisioning source layout changed")
endif()
list(APPEND LOCAL_WIFI_SOURCES "${LOCAL_WIFI_DIR}/wifi_configuration_ap.cc")
set_property(TARGET ${WIFI_LIB} PROPERTY SOURCES "${LOCAL_WIFI_SOURCES}")
target_include_directories(${WIFI_LIB} BEFORE PUBLIC "${LOCAL_WIFI_DIR}/include")
target_add_binary_data(${WIFI_LIB} "${LOCAL_WIFI_DIR}/assets/wifi_local.html" TEXT
    RENAME_TO "wifi_configuration_html")
set_source_files_properties("${LOCAL_BUILD_DIR}/wifi_local.html.S"
    TARGET_DIRECTORY ${WIFI_LIB} PROPERTIES GENERATED TRUE)
add_custom_target(local_wifi_page DEPENDS "${LOCAL_BUILD_DIR}/wifi_local.html.S")
add_dependencies(${WIFI_LIB} local_wifi_page)

# Use target_compile_definitions to define BOARD_TYPE, BOARD_NAME
# If BOARD_NAME is empty, use BOARD_TYPE
if(NOT BOARD_NAME)
    set(BOARD_NAME ${BOARD_TYPE})
endif()
target_compile_definitions(${COMPONENT_LIB}
                    PRIVATE BOARD_TYPE=\"${BOARD_TYPE}\" BOARD_NAME=\"${BOARD_NAME}\"
                    PRIVATE BUILTIN_TEXT_FONT=${BUILTIN_TEXT_FONT} BUILTIN_ICON_FONT=${BUILTIN_ICON_FONT}
                    )

# The pinned esp-ml307 WebSocket parser does not enforce SetReceiveBufferSize while
# accumulating frames. Use the reviewed bounded derivative and a Bridge-only factory.
# MQTT, generic UDP and cellular-modem implementations are not compiled.
find_component_by_pattern("^78__esp-ml307$" ESP_ML307_COMPONENT ESP_ML307_COMPONENT_PATH)
if(NOT ESP_ML307_COMPONENT)
    message(FATAL_ERROR "Pinned esp-ml307 component was not resolved")
endif()
idf_component_get_property(ESP_ML307_LIB ${ESP_ML307_COMPONENT} COMPONENT_LIB)
get_target_property(ESP_ML307_SOURCES ${ESP_ML307_LIB} SOURCES)
set(ESP_ML307_FILTERED_SOURCES "")
set(ESP_ML307_WEBSOCKET_REMOVED FALSE)
foreach(ESP_ML307_SOURCE IN LISTS ESP_ML307_SOURCES)
    get_filename_component(
        ESP_ML307_SOURCE_ABSOLUTE
        "${ESP_ML307_SOURCE}"
        ABSOLUTE
        BASE_DIR "${ESP_ML307_COMPONENT_PATH}"
    )
    if(ESP_ML307_SOURCE_ABSOLUTE STREQUAL "${ESP_ML307_COMPONENT_PATH}/src/web_socket.cc")
        set(ESP_ML307_WEBSOCKET_REMOVED TRUE)
    elseif(ESP_ML307_SOURCE_ABSOLUTE MATCHES "/src/(esp/esp_(tcp|ssl)|http_client)\\.cc$")
        list(APPEND ESP_ML307_FILTERED_SOURCES "${ESP_ML307_SOURCE}")
    endif()
endforeach()
if(NOT ESP_ML307_WEBSOCKET_REMOVED)
    message(FATAL_ERROR "Pinned esp-ml307 WebSocket source layout changed")
endif()
list(APPEND ESP_ML307_FILTERED_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/../components/stackchan_bridge_client/esp_network.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../components/stackchan_bridge_client/web_socket.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../components/stackchan_bridge_client/websocket_pong.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/../components/stackchan_bridge_client/websocket_handshake.cpp"
)
set_property(TARGET ${ESP_ML307_LIB} PROPERTY SOURCES "${ESP_ML307_FILTERED_SOURCES}")
target_include_directories(${ESP_ML307_LIB} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/../components/stackchan_bridge_client/include"
)

# Add generation rules
add_custom_command(
    OUTPUT ${LANG_HEADER}
    COMMAND python ${XIAOZHI_MAIN_DIR}/../scripts/gen_lang.py
            --language "${LANG_DIR}"
            --output "${LANG_HEADER}"
    DEPENDS
        ${LANG_JSON}
        ${XIAOZHI_MAIN_DIR}/../scripts/gen_lang.py
    COMMENT "Generating ${LANG_DIR} language config"
)

# Force build generation dependencies
add_custom_target(lang_header ALL
    DEPENDS ${LANG_HEADER}
)

# Find ESP-SR component dynamically
find_component_by_pattern("espressif__esp-sr" ESP_SR_COMPONENT ESP_SR_COMPONENT_PATH)
if(ESP_SR_COMPONENT_PATH)
    set(ESP_SR_MODEL_PATH "${ESP_SR_COMPONENT_PATH}/model")
endif()

# Find xiaozhi-fonts component dynamically
find_component_by_pattern("xiaozhi-fonts" XIAOZHI_FONTS_COMPONENT XIAOZHI_FONTS_COMPONENT_PATH)
if(XIAOZHI_FONTS_COMPONENT_PATH)
    # The locked component's font shapes have unresolved redistribution provenance.
    # Keep its licensed helpers/Twemoji and compile only our reviewed replacement glyphs.
    include("${CMAKE_CURRENT_SOURCE_DIR}/../cmake/release_fonts.cmake")
    idf_component_get_property(XIAOZHI_FONTS_LIB ${XIAOZHI_FONTS_COMPONENT} COMPONENT_LIB)
    set(STACKCHAN_RELEASE_FONTS "${CMAKE_CURRENT_SOURCE_DIR}/../release-fonts")
    stackchan_use_release_fonts(${XIAOZHI_FONTS_LIB}
        "${XIAOZHI_FONTS_COMPONENT_PATH}" "${STACKCHAN_RELEASE_FONTS}/src")

    # Stage only the reviewed text font and CC-BY-4.0 emoji for the asset partition.
    set(XIAOZHI_FONTS_PATH "${CMAKE_BINARY_DIR}/stackchan_fonts")
    file(MAKE_DIRECTORY "${XIAOZHI_FONTS_PATH}/cbin" "${XIAOZHI_FONTS_PATH}/png")
    configure_file("${STACKCHAN_RELEASE_FONTS}/cbin/font_stackchan_common_20_4.bin"
        "${XIAOZHI_FONTS_PATH}/cbin/font_stackchan_common_20_4.bin" COPYONLY)
    file(COPY "${XIAOZHI_FONTS_COMPONENT_PATH}/png/twemoji_64"
        DESTINATION "${XIAOZHI_FONTS_PATH}/png")
else()
    message(FATAL_ERROR "Pinned xiaozhi-fonts helpers were not resolved")
endif()

if(CONFIG_BOARD_TYPE_ESP_HI)
set(URL "https://github.com/espressif2022/image_player/raw/main/test_apps/test_8bit")
set(EMOJI_DIR "${CMAKE_BINARY_DIR}/emoji")
file(MAKE_DIRECTORY ${EMOJI_DIR})

# List all files to download
set(FILES_TO_DOWNLOAD "")
list(APPEND FILES_TO_DOWNLOAD "Anger_enter.aaf" "Anger_loop.aaf" "Anger_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "happy_enter.aaf" "happy_loop.aaf" "happ_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "sad_enter.aaf" "sad_loop.aaf" "sad_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "scorn_enter.aaf" "scorn_loop.aaf" "scorn_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "left_enter.aaf" "left_loop.aaf" "left_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "right_enter.aaf" "right_loop.aaf" "right_return.aaf")
list(APPEND FILES_TO_DOWNLOAD "asking.aaf" "blink_once.aaf" "blink_quick.aaf")
list(APPEND FILES_TO_DOWNLOAD "connecting.aaf" "panic_enter.aaf" "panic_loop.aaf")
list(APPEND FILES_TO_DOWNLOAD "panic_return.aaf" "wake.aaf")

foreach(FILENAME IN LISTS FILES_TO_DOWNLOAD)
    set(REMOTE_FILE "${URL}/${FILENAME}")
    set(LOCAL_FILE "${EMOJI_DIR}/${FILENAME}")
    
    # Check if local file exists
    if(EXISTS ${LOCAL_FILE})
        message(STATUS "File ${FILENAME} already exists, skipping download")
    else()
        message(STATUS "Downloading ${FILENAME}")
        file(DOWNLOAD ${REMOTE_FILE} ${LOCAL_FILE}
             STATUS DOWNLOAD_STATUS)
        list(GET DOWNLOAD_STATUS 0 STATUS_CODE)
        if(NOT STATUS_CODE EQUAL 0)
            message(FATAL_ERROR "Failed to download ${FILENAME} from ${URL}")
        endif()
    endif()
endforeach()

endif()

set(DEFAULT_ASSETS_EXTRA_FILES "${CMAKE_CURRENT_SOURCE_DIR}/assets/assets_bin")

# Function to build default assets based on configuration
function(build_default_assets_bin)
    # Set output path for generated assets.bin
    set(GENERATED_ASSETS_BIN "${CMAKE_BINARY_DIR}/generated_assets.bin")
    
    # Prepare arguments for build script
    set(BUILD_ARGS
        "--sdkconfig" "${SDKCONFIG}"
        "--output" "${GENERATED_ASSETS_BIN}"
    )
    
    # Add builtin text font if defined
    if(BUILTIN_TEXT_FONT)
        list(APPEND BUILD_ARGS "--builtin_text_font" "${BUILTIN_TEXT_FONT}")
    endif()
    
    # Add default emoji collection if defined
    if(DEFAULT_EMOJI_COLLECTION)
        list(APPEND BUILD_ARGS "--emoji_collection" "${DEFAULT_EMOJI_COLLECTION}")
    endif()
    
    # Add default assets extra files if defined
    if(DEFAULT_ASSETS_EXTRA_FILES)
        list(APPEND BUILD_ARGS "--extra_files" "${DEFAULT_ASSETS_EXTRA_FILES}")
    endif()

    # Track membership too: removing a cloud icon must invalidate an existing bundle.
    file(GLOB EXTRA_ASSET_FILES CONFIGURE_DEPENDS "${DEFAULT_ASSETS_EXTRA_FILES}/*")
    set(ASSET_INPUT_LIST "${CMAKE_BINARY_DIR}/asset-inputs.txt")
    file(GENERATE OUTPUT "${ASSET_INPUT_LIST}" CONTENT "${EXTRA_ASSET_FILES}\n")
    
    list(APPEND BUILD_ARGS "--esp_sr_model_path" "${ESP_SR_MODEL_PATH}")
    list(APPEND BUILD_ARGS "--xiaozhi_fonts_path" "${XIAOZHI_FONTS_PATH}")
    
    # Create custom command to build assets
    add_custom_command(
        OUTPUT ${GENERATED_ASSETS_BIN}
        COMMAND python ${XIAOZHI_MAIN_DIR}/../scripts/build_default_assets.py ${BUILD_ARGS}
        DEPENDS
            ${SDKCONFIG}
            ${XIAOZHI_MAIN_DIR}/../scripts/build_default_assets.py
            ${STACKCHAN_RELEASE_FONTS}/cbin/font_stackchan_common_20_4.bin
            ${EXTRA_ASSET_FILES}
            ${ASSET_INPUT_LIST}
        COMMENT "Building default assets.bin based on configuration"
        VERBATIM
    )
    
    # Create target for generated assets
    add_custom_target(generated_default_assets ALL
        DEPENDS ${GENERATED_ASSETS_BIN}
    )
    
    # Set the generated file path in parent scope
    set(GENERATED_ASSETS_LOCAL_FILE ${GENERATED_ASSETS_BIN} PARENT_SCOPE)
    
    message(STATUS "Default assets build configured: ${GENERATED_ASSETS_BIN}")
endfunction()


# Function to get local assets file path (handles both URL and local file)
function(get_assets_local_file assets_source assets_local_file_var)
    # Check if it's a URL (starts with http:// or https://)
    if(assets_source MATCHES "^https?://")
        # It's a URL, download it
        get_filename_component(ASSETS_FILENAME "${assets_source}" NAME)
        set(ASSETS_LOCAL_FILE "${CMAKE_BINARY_DIR}/${ASSETS_FILENAME}")
        set(ASSETS_TEMP_FILE "${CMAKE_BINARY_DIR}/${ASSETS_FILENAME}.tmp")
        
        # Check if local file exists
        if(EXISTS ${ASSETS_LOCAL_FILE})
            message(STATUS "Assets file ${ASSETS_FILENAME} already exists, skipping download")
        else()
            message(STATUS "Downloading ${ASSETS_FILENAME}")
            
            # Clean up any existing temp file
            if(EXISTS ${ASSETS_TEMP_FILE})
                file(REMOVE ${ASSETS_TEMP_FILE})
            endif()
            
            # Download to temporary file first
            file(DOWNLOAD ${assets_source} ${ASSETS_TEMP_FILE}
                 STATUS DOWNLOAD_STATUS)
            list(GET DOWNLOAD_STATUS 0 STATUS_CODE)
            if(NOT STATUS_CODE EQUAL 0)
                # Clean up temp file on failure
                if(EXISTS ${ASSETS_TEMP_FILE})
                    file(REMOVE ${ASSETS_TEMP_FILE})
                endif()
                message(FATAL_ERROR "Failed to download ${ASSETS_FILENAME} from ${assets_source}")
            endif()
            
            # Move temp file to final location (atomic operation)
            file(RENAME ${ASSETS_TEMP_FILE} ${ASSETS_LOCAL_FILE})
            message(STATUS "Successfully downloaded ${ASSETS_FILENAME}")
        endif()
    else()
        # It's a local file path
        if(IS_ABSOLUTE "${assets_source}")
            set(ASSETS_LOCAL_FILE "${assets_source}")
        else()
            set(ASSETS_LOCAL_FILE "${XIAOZHI_MAIN_DIR}/${assets_source}")
        endif()
        
        # Check if local file exists
        if(NOT EXISTS ${ASSETS_LOCAL_FILE})
            message(FATAL_ERROR "Assets file not found: ${ASSETS_LOCAL_FILE}")
        endif()
        
        message(STATUS "Using assets file: ${ASSETS_LOCAL_FILE}")
    endif()
    
    set(${assets_local_file_var} ${ASSETS_LOCAL_FILE} PARENT_SCOPE)
endfunction()


partition_table_get_partition_info(size "--partition-name assets" "size")
partition_table_get_partition_info(offset "--partition-name assets" "offset")
if ("${size}" AND "${offset}")
    # Flash assets based on configuration
    if(CONFIG_FLASH_DEFAULT_ASSETS)
        # Build default assets based on configuration
        build_default_assets_bin()
        esptool_py_flash_to_partition(flash "assets" "${GENERATED_ASSETS_LOCAL_FILE}")
        message(STATUS "Generated default assets flash configured: ${GENERATED_ASSETS_LOCAL_FILE} -> assets partition")
    elseif(CONFIG_FLASH_CUSTOM_ASSETS)
        # Flash custom assets
        get_assets_local_file("${CONFIG_CUSTOM_ASSETS_FILE}" ASSETS_LOCAL_FILE)
        esptool_py_flash_to_partition(flash "assets" "${ASSETS_LOCAL_FILE}")
        message(STATUS "Custom assets flash configured: ${ASSETS_LOCAL_FILE} -> assets partition")
    elseif(CONFIG_FLASH_EXPRESSION_ASSETS)
        set(ASSETS_NAME "expression_assets")
        set(ASSETS_PARTITION "assets")
        set(ASSETS_FILE "${CMAKE_BINARY_DIR}/${ASSETS_NAME}.bin")

        build_speaker_assets_bin("${ASSETS_PARTITION}" ${EMOTE_RESOLUTION} ${ASSETS_FILE} ${CONFIG_MMAP_FILE_NAME_LENGTH})
        message(STATUS "Generated emote assets: ${ASSETS_FILE} -> ${ASSETS_PARTITION} partition")
        esptool_py_flash_to_partition(flash "${ASSETS_PARTITION}" "${ASSETS_FILE}")
    elseif(CONFIG_FLASH_NONE_ASSETS)
        message(STATUS "Assets flashing disabled (FLASH_NONE_ASSETS)")
    endif()
else()
    message(STATUS "Assets partition not found, using v1 partition table")
endif()
