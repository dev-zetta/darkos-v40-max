#!/bin/sh
# Sourced after the common ARMHF wrapper has set its Mesa environment.
v40_sm64_route() {
    [ "$#" -eq 5 ] || return 0
    [ "$1" = -c ] && [ "$2" = /home/ark/.config/retroarch32/retroarch.cfg ] &&
        [ "$3" = -L ] && [ "$4" = /home/ark/.config/retroarch32/cores/parallel_n64_libretro.so ] &&
        [ "$5" = "/roms/n64/Super Mario 64.n64" ] || return 0

    v40_sm64=/opt/retroarch/v40-mainline/sm64
    [ -x "$v40_sm64/retroarch32" ] &&
        [ -r "$v40_sm64/jit/parallel_n64_libretro.so" ] &&
        [ -r "$v40_sm64/pacing.cfg" ] &&
        [ -f "$5" ] && [ ! -L "$5" ] || return 0
    printf '%s  %s\n' 8ca0178cb5c7c95bdc5dc9674665996a2d7210f94fb014e7f8b68910c77c3ecb "$5" |
        /usr/bin/sha256sum -c --status || return 0

    v40_sm64_cache=/home/ark/.cache/v40-sm64
    [ ! -L /home/ark/.cache ] && [ ! -L "$v40_sm64_cache" ] || return 0
    (umask 077; mkdir -p -- "$v40_sm64_cache") || return 0
    [ -d "$v40_sm64_cache" ] && [ ! -L "$v40_sm64_cache" ] &&
        [ "$(stat -c '%u:%a' -- "$v40_sm64_cache")" = "$(id -u):700" ] &&
        [ -w "$v40_sm64_cache" ] || return 0

    export MESA_SHADER_CACHE_DIR="$v40_sm64_cache" MESA_SHADER_CACHE_MAX_SIZE=32M
    export MESA_SHADER_CACHE_DISABLE=false
    export RETROARCH_V40_DRM_WORKER=1 V40_JIT_WARMUP=1 V40_RICE_LAZY_COMBINER=1
    # Use Debian's Mesa backend discovery for the verified ARMHF route.
    unset GBM_BACKENDS_PATH LIBGL_DRIVERS_PATH
    unset V40_N64_STOP_AFTER_JAL
    exec "$v40_sm64/retroarch32" "--appendconfig=$v40_sm64/pacing.cfg" \
        "$1" "$2" "$3" "$v40_sm64/jit/parallel_n64_libretro.so" "$5"
}
v40_sm64_route "$@"
