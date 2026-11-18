/* SPDX-License-Identifier: MIT */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES/gl.h>
#include <stdio.h>
#include <stdlib.h>
#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "failed: %s EGL=%x\n", #expr, eglGetError()); return 1; } } while (0)
int main(void)
{
    EGLDisplay display = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
    EGLint major, minor, count;
    EGLConfig config;
    EGLint attributes[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8, EGL_NONE };
    EGLint context_attributes[] = { EGL_CONTEXT_CLIENT_VERSION, 1, EGL_NONE };
    EGLint surface_attributes[] = { EGL_WIDTH, 8, EGL_HEIGHT, 8, EGL_NONE };
    unsigned char pixel[4];
    CHECK(display != EGL_NO_DISPLAY);
    CHECK(eglInitialize(display, &major, &minor));
    CHECK(eglBindAPI(EGL_OPENGL_ES_API));
    CHECK(eglChooseConfig(display, attributes, &config, 1, &count) && count == 1);
    EGLSurface surface = eglCreatePbufferSurface(display, config, surface_attributes);
    CHECK(surface != EGL_NO_SURFACE);
    EGLContext context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
    CHECK(context != EGL_NO_CONTEXT);
    CHECK(eglMakeCurrent(display, surface, surface, context));
    printf("GL_VERSION=%s\nGL_RENDERER=%s\n", glGetString(GL_VERSION), glGetString(GL_RENDERER));
    glClearColor(0.25f, 0.5f, 0.75f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glFinish();
    glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    CHECK(glGetError() == GL_NO_ERROR);
    CHECK(abs((int)pixel[0]-64)<=2 && abs((int)pixel[1]-128)<=2 && abs((int)pixel[2]-191)<=2 && pixel[3]==255);
    printf("GLES1_CONTEXT_AND_PIXEL_READBACK_PASS %u,%u,%u,%u\n",pixel[0],pixel[1],pixel[2],pixel[3]);
    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroyContext(display, context);eglDestroySurface(display, surface);eglTerminate(display);
    return 0;
}
