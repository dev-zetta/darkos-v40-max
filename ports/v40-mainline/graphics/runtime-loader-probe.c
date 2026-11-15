/* SPDX-License-Identifier: MIT */
#include <dlfcn.h>
#include <stdio.h>
int main(int argc, char **argv)
{
    for (int i = 1; i < argc; i++) {
        void *handle = dlopen(argv[i], RTLD_NOW | RTLD_LOCAL);
        if (!handle) { fprintf(stderr, "%s: %s\n", argv[i], dlerror()); return 1; }
        printf("loaded %s\n", argv[i]);
        dlclose(handle);
    }
    return 0;
}
