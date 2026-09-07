# Keep the MIT runtime helpers and CC-BY-4.0 Twemoji data from the locked component.
# Glyph data comes exclusively from our pinned, licensed font inputs.
function(stackchan_use_release_fonts TARGET UPSTREAM_DIR GENERATED_DIR)
    set(REVIEWED_SOURCES
        "${UPSTREAM_DIR}/src/cbin_font.c"
        "${UPSTREAM_DIR}/src/font_awesome.c"
        "${UPSTREAM_DIR}/src/font_emoji_32.c"
        "${UPSTREAM_DIR}/src/font_emoji_64.c"
    )
    file(GLOB TWEMOJI_SOURCES "${UPSTREAM_DIR}/src/emoji/*.c")
    file(GLOB GENERATED_SOURCES "${GENERATED_DIR}/*.c")
    if(NOT GENERATED_SOURCES)
        message(FATAL_ERROR "Reviewed StackChan fonts are missing")
    endif()
    set_property(TARGET ${TARGET} PROPERTY SOURCES
        ${REVIEWED_SOURCES} ${TWEMOJI_SOURCES} ${GENERATED_SOURCES})
endfunction()
