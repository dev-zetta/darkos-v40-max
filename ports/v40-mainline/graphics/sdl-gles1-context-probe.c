#define _GNU_SOURCE
#include <SDL.h>
#include <GLES/gl.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

/* Exercise the same SDL window/GLES1 setup as the frontend using a pbuffer.
 * This validates the private user-space stack, not a physical KMS modeset. */
int main(void)
{
    Dl_info library;
    SDL_Window *window;
    SDL_GLContext context;
    unsigned char pixel[4];
    const unsigned char expected[4] = {64, 128, 191, 255};
    int index;
    if (!dladdr((void *)SDL_Init, &library) ||
        !strstr(library.dli_fname, "mainline-boot-fix-20261114")) {
        fprintf(stderr, "Private rebuilt SDL was not selected\n");
        return 1;
    }
    printf("SDL library: %s\n", library.dli_fname);
    if (SDL_Init(SDL_INIT_VIDEO)) {
        fprintf(stderr, "SDL video: %s\n", SDL_GetError());
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 1);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    window = SDL_CreateWindow("mainline SDL probe", 0, 0, 64, 64,
                              SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!window) {
        fprintf(stderr, "SDL window: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }
    context = SDL_GL_CreateContext(window);
    if (!context || SDL_GL_MakeCurrent(window, context)) {
        fprintf(stderr, "SDL GLES1 context: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }
    if (!glGetString(GL_VERSION)) {
        fprintf(stderr, "No current GLES context\n");
        return 1;
    }
    printf("GLES: %s; renderer: %s\n", glGetString(GL_VERSION), glGetString(GL_RENDERER));
    glClearColor(0.25f, 0.5f, 0.75f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    if (glGetError() != GL_NO_ERROR) {
        fprintf(stderr, "GLES pixel readback failed\n");
        return 1;
    }
    for (index = 0; index < 4; ++index) {
        if (pixel[index] != expected[index]) {
            fprintf(stderr, "Pixel channel %d: got %u, expected %u\n",
                    index, pixel[index], expected[index]);
            return 1;
        }
    }
    SDL_GL_DeleteContext(context);
    SDL_DestroyWindow(window);
    SDL_Quit();
    puts("SDL_GLES1_WINDOW_PIXEL_PASS RGBA=64,128,191,255");
    return 0;
}
