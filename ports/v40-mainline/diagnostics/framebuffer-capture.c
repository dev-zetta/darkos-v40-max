// SPDX-License-Identifier: MIT
/* Read one current linear KMS framebuffer without acquiring master or changing modes. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

#define MAX_DIMENSION 4096U
#define MAX_BYTES (64U * 1024U * 1024U)

/* Support only the observed 32-bit linear scanout formats. Alpha is reported,
 * not applied: VOP's primary window disables blending for ARGB scanout. */
static int write_ppm(const char *path, const uint8_t *data, uint32_t width,
                     uint32_t height, uint32_t pitch, uint32_t format,
                     uint32_t framebuffer)
{
    bool bgr = format == DRM_FORMAT_ARGB8888 || format == DRM_FORMAT_XRGB8888;
    bool alpha = format == DRM_FORMAT_ARGB8888 || format == DRM_FORMAT_ABGR8888;
    uint64_t sums[4] = {0}, black = 0, count = (uint64_t)width * height;
    unsigned minimum[4] = {255, 255, 255, 255}, maximum[4] = {0};
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    FILE *out;
    if (fd < 0) { perror("create PPM (must not exist)"); return -1; }
    out = fdopen(fd, "wb");
    if (!out) { close(fd); unlink(path); return -1; }
    bool failed = fprintf(out, "P6\n%u %u\n255\n", width, height) < 0;
    for (uint32_t y = 0; y < height && !failed; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            const uint8_t *source = data + (size_t)y * pitch + x * 4U;
            uint8_t rgba[4] = {source[bgr ? 2 : 0], source[1], source[bgr ? 0 : 2], alpha ? source[3] : 255};
            for (unsigned channel = 0; channel < 4; ++channel) {
                sums[channel] += rgba[channel];
                if (rgba[channel] < minimum[channel]) minimum[channel] = rgba[channel];
                if (rgba[channel] > maximum[channel]) maximum[channel] = rgba[channel];
            }
            black += rgba[0] == 0 && rgba[1] == 0 && rgba[2] == 0;
            if (fwrite(rgba, 1, 3, out) != 3) { failed = true; break; }
        }
    }
    if (fflush(out) || fsync(fd)) failed = true;
    if (fclose(out)) failed = true;
    if (failed) { perror("write PPM"); unlink(path); return -1; }
    printf("{\"framebuffer\":%u,\"width\":%u,\"height\":%u,\"pitch\":%u,\"fourcc\":%u,\"modifier\":0,\"sample_pixels\":%" PRIu64 ",\"black_pixels\":%" PRIu64 ",\"channel_order\":\"RGBA\",\"mean\":[%.3f,%.3f,%.3f,%.3f],\"min\":[%u,%u,%u,%u],\"max\":[%u,%u,%u,%u],\"alpha_applied\":false,\"display_mutated\":false}\n",
           framebuffer, width, height, pitch, format, count, black,
           (double)sums[0]/count, (double)sums[1]/count, (double)sums[2]/count, (double)sums[3]/count,
           minimum[0], minimum[1], minimum[2], minimum[3], maximum[0], maximum[1], maximum[2], maximum[3]);
    return 0;
}

static void close_handles(int fd, drmModeFB2 *fb)
{
    for (unsigned i = 0; i < 4; ++i) {
        if (!fb->handles[i]) continue;
        bool previous = false;
        for (unsigned j = 0; j < i; ++j) previous |= fb->handles[j] == fb->handles[i];
        if (!previous) drmCloseBufferHandle(fd, fb->handles[i]);
    }
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--self-test")) {
        /* Padded BGRA: red(alpha0), green(alpha64), blue(alpha128), white(alpha255).
         * The expected PPM remains opaque full-bright RGB for all four pixels. */
        const uint8_t pixels[] = {0,0,255,0, 0,255,0,64, 99,99,99,99,
                                  255,0,0,128, 255,255,255,255, 99,99,99,99};
        return write_ppm(argv[2], pixels, 2, 2, 12, DRM_FORMAT_ARGB8888, 0) ? 1 : 0;
    }
    if (argc != 3 || strcmp(argv[1], "/dev/dri/card0")) { fprintf(stderr, "Usage: %s /dev/dri/card0 OUTPUT.ppm\n", argv[0]); return 2; }
    int result = 1, fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    uint32_t framebuffer = 0;
    drmModeRes *resources = NULL;
    drmModeFB2 *fb = NULL;
    void *mapping = MAP_FAILED;
    size_t length = 0;
    if (fd < 0) { perror("open card0"); goto done; }
    resources = drmModeGetResources(fd);
    if (!resources) { perror("get KMS resources"); goto done; }
    for (int i = 0; i < resources->count_crtcs; ++i) {
        drmModeCrtc *crtc = drmModeGetCrtc(fd, resources->crtcs[i]);
        if (!crtc) { perror("get CRTC"); goto done; }
        if (crtc->mode_valid && crtc->buffer_id) {
            if (framebuffer) { drmModeFreeCrtc(crtc); fprintf(stderr,"Multiple active CRTCs; refusing ambiguous capture\n"); goto done; }
            framebuffer = crtc->buffer_id;
        }
        drmModeFreeCrtc(crtc);
    }
    if (!framebuffer) { fprintf(stderr, "No active CRTC framebuffer\n"); goto done; }
    fb = drmModeGetFB2(fd, framebuffer);
    if (!fb) { perror("get framebuffer metadata"); goto done; }
    if (!fb->handles[0]) { fprintf(stderr, "Framebuffer handle hidden: run as root with CAP_SYS_ADMIN\n"); goto done; }
    if (!fb->width || !fb->height || fb->width > MAX_DIMENSION || fb->height > MAX_DIMENSION ||
        fb->modifier != DRM_FORMAT_MOD_LINEAR || fb->offsets[0] ||
        fb->handles[1] || fb->handles[2] || fb->handles[3] ||
        fb->pitches[0] < fb->width * 4U ||
        (uint64_t)fb->height * fb->pitches[0] > MAX_BYTES ||
        (fb->pixel_format != DRM_FORMAT_ARGB8888 && fb->pixel_format != DRM_FORMAT_XRGB8888 &&
         fb->pixel_format != DRM_FORMAT_ABGR8888 && fb->pixel_format != DRM_FORMAT_XBGR8888)) {
        fprintf(stderr, "Unsupported framebuffer layout; capture skipped\n"); goto done;
    }
    struct drm_mode_map_dumb map = {.handle = fb->handles[0]};
    if (ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) { perror("map framebuffer handle"); goto done; }
    length = (size_t)fb->height * fb->pitches[0];
    mapping = mmap(NULL, length, PROT_READ, MAP_SHARED, fd, map.offset);
    if (mapping == MAP_FAILED) { perror("mmap framebuffer read-only"); goto done; }
    result = write_ppm(argv[2], mapping, fb->width, fb->height, fb->pitches[0], fb->pixel_format, framebuffer) ? 1 : 0;
 done:
    if (mapping != MAP_FAILED) munmap(mapping, length);
    if (fb) { close_handles(fd, fb); drmModeFreeFB2(fb); }
    if (resources) drmModeFreeResources(resources);
    if (fd >= 0) close(fd);
    return result;
}
