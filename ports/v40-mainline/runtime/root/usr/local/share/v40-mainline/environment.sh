# Kernel-selected private Mesa; literal $LIB expands in each target loader.
if [ "$(uname -r)" = "7.3.4-v40.1" ]; then
    export LD_LIBRARY_PATH='/usr/local/lib/v40-mainline/$LIB'${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
    export LIBGL_DRIVERS_PATH='/usr/local/lib/v40-mainline/$LIB/dri'
    export GBM_BACKENDS_PATH='/usr/local/lib/v40-mainline/$LIB/gbm'
    export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/local/share/v40-mainline/50_mesa.json
    export LIBGL_DEBUG=${LIBGL_DEBUG:-verbose}
    export EGL_LOG_LEVEL=${EGL_LOG_LEVEL:-debug}
fi
