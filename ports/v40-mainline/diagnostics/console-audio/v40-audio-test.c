// SPDX-License-Identifier: MIT
#define _POSIX_C_SOURCE 200809L
#include <alsa/asoundlib.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <math.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define RATE 44100U
#define PERIOD 1024U
#ifndef BUFFER
#define BUFFER 2048U
#endif
#define PEAK 8192
#define CYCLE (RATE * 2U)
#ifndef MAX_SECONDS
#define MAX_SECONDS 105.0
#endif
#ifndef SOURCE_SECONDS
#define SOURCE_SECONDS 0U
#endif
#ifndef WAIT_TIMEOUT_MS
#define WAIT_TIMEOUT_MS 100
#endif
#ifndef WAIT_LOG_LIMIT
#define WAIT_LOG_LIMIT 0U
#endif
#ifndef PERIOD_EVENT
#define PERIOD_EVENT 0
#endif
#ifndef WHOLE_PERIOD_WRITES
#define WHOLE_PERIOD_WRITES 1
#endif
_Static_assert(SOURCE_SECONDS <= 52U, "Source duration exceeds the reference");
_Static_assert(WAIT_TIMEOUT_MS > 0 && WAIT_TIMEOUT_MS <= 1000, "Invalid wait timeout");
_Static_assert(PERIOD_EVENT == 0 || PERIOD_EVENT == 1, "Invalid period-event mode");
_Static_assert(WHOLE_PERIOD_WRITES == 0 || WHOLE_PERIOD_WRITES == 1, "Invalid write gating mode");

struct phase { const char *name; unsigned seconds; int mode; };
static const struct phase phases[] = {
    {"digital_silence_start", 12U, 0}, {"left_only", 8U, 1},
    {"right_only", 8U, 2}, {"both_same", 8U, 3},
    {"both_opposite", 8U, 4}, {"digital_silence_end", 8U, 0}
};
static volatile sig_atomic_t stopped;
static int16_t cycle[CYCLE];
static uint64_t boundary[7];
static uint64_t stream_frames(void) { return SOURCE_SECONDS ? (uint64_t)SOURCE_SECONDS * RATE : boundary[6]; }
static void stop_signal(int signum) { (void)signum; stopped = 1; }
static double clock_seconds(clockid_t id) {
    struct timespec t;
    if (clock_gettime(id, &t) != 0) { perror("clock_gettime"); exit(2); }
    return (double)t.tv_sec + (double)t.tv_nsec / 1000000000.0;
}
static void initialize(void) {
    const unsigned tone = RATE * 2U / 5U, fade = RATE / 50U;
    for (unsigned i = 0; i < CYCLE; ++i) {
        const int j = (int)i - (int)(RATE / 2U);
        if (j >= 0 && (unsigned)j < tone) {
            const double a = (double)j / fade;
            const double b = (double)(tone - 1U - (unsigned)j) / fade;
            const double env = fmin(1.0, fmin(a, b));
            cycle[i] = (int16_t)lround(PEAK * env * sin(2.0 * 3.14159265358979323846 * 660.0 * j / RATE));
        }
    }
    for (unsigned i = 0; i < 6U; ++i) boundary[i + 1U] = boundary[i] + (uint64_t)phases[i].seconds * RATE;
}
static unsigned phase_at(uint64_t frame) {
    unsigned i = 0;
    while (i < 5U && frame >= boundary[i + 1U]) ++i;
    return i;
}
static void fill(int16_t *out, uint64_t start, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        const uint64_t f = start + i;
        const unsigned p = phase_at(f);
        const int16_t a = cycle[(f - boundary[p]) % CYCLE];
        const int mode = phases[p].mode;
        out[2U * i] = mode == 1 || mode == 3 || mode == 4 ? a : 0;
        out[2U * i + 1U] = mode == 2 || mode == 3 ? a : mode == 4 ? (int16_t)-a : 0;
    }
}
static int dump_reference(const char *path) {
    FILE *out = fopen(path, "wbx");
    if (!out) { perror("reference output"); return 2; }
    int16_t block[PERIOD * 2U];
    for (uint64_t f = 0; f < stream_frames();) {
        const size_t n = stream_frames() - f < PERIOD ? (size_t)(stream_frames() - f) : PERIOD;
        fill(block, f, n);
        if (fwrite(block, sizeof(int16_t) * 2U, n, out) != n) { perror("reference write"); fclose(out); return 2; }
        f += n;
    }
    if (fclose(out) != 0) { perror("reference close"); return 2; }
    printf("{\"event\":\"reference_dump\",\"frames\":%" PRIu64 ",\"rate\":%u,\"channels\":2,\"peak\":%d}\n", stream_frames(), RATE, PEAK);
    return 0;
}
static int fail(const char *op, int error) {
    fprintf(stderr, "{\"event\":\"alsa_error\",\"operation\":\"%s\",\"code\":%d}\n", op, error);
    return 2;
}
static int playback(void) {
    snd_pcm_t *pcm = NULL;
    snd_pcm_hw_params_t *hw = NULL;
    snd_pcm_sw_params_t *sw = NULL;
    snd_pcm_status_t *status = NULL;
    int result = 2, rc, tty = -1;
    const double started = clock_seconds(CLOCK_MONOTONIC_RAW);
    const double cpu_started = clock_seconds(CLOCK_PROCESS_CPUTIME_ID);
    uint64_t written = 0, partial = 0, waits = 0, wait_timeouts = 0;
    double wait_seconds = 0.0, wait_max = 0.0, write_seconds = 0.0, write_max = 0.0, tty_seconds = 0.0;
    int last_phase = -1;
    double next_sample = started;
    int16_t block[PERIOD * 2U];
#define CHECK(call) do { rc = (call); if (rc < 0) { fail(#call, rc); goto done; } } while (0)
    CHECK(snd_pcm_open(&pcm, "v40_console", SND_PCM_STREAM_PLAYBACK, SND_PCM_NONBLOCK));
    CHECK(snd_pcm_hw_params_malloc(&hw));
    CHECK(snd_pcm_sw_params_malloc(&sw));
    CHECK(snd_pcm_status_malloc(&status));
    CHECK(snd_pcm_hw_params_any(pcm, hw));
    CHECK(snd_pcm_hw_params_set_rate_resample(pcm, hw, 0));
    CHECK(snd_pcm_hw_params_set_access(pcm, hw, SND_PCM_ACCESS_RW_INTERLEAVED));
    CHECK(snd_pcm_hw_params_set_format(pcm, hw, SND_PCM_FORMAT_S16_LE));
    CHECK(snd_pcm_hw_params_set_channels(pcm, hw, 2));
    CHECK(snd_pcm_hw_params_set_rate(pcm, hw, RATE, 0));
    CHECK(snd_pcm_hw_params_set_period_size(pcm, hw, PERIOD, 0));
    CHECK(snd_pcm_hw_params_set_buffer_size(pcm, hw, BUFFER));
    CHECK(snd_pcm_hw_params(pcm, hw));
    unsigned period_wakeup = 0;
    CHECK(snd_pcm_hw_params_get_period_wakeup(pcm, hw, &period_wakeup));
    CHECK(snd_pcm_sw_params_current(pcm, sw));
    CHECK(snd_pcm_sw_params_set_avail_min(pcm, sw, PERIOD));
    CHECK(snd_pcm_sw_params_set_start_threshold(pcm, sw, BUFFER));
    CHECK(snd_pcm_sw_params_set_stop_threshold(pcm, sw, BUFFER));
    if (PERIOD_EVENT) CHECK(snd_pcm_sw_params_set_period_event(pcm, sw, 1));
    CHECK(snd_pcm_sw_params_set_tstamp_mode(pcm, sw, SND_PCM_TSTAMP_ENABLE));
    CHECK(snd_pcm_sw_params_set_tstamp_type(pcm, sw, SND_PCM_TSTAMP_TYPE_MONOTONIC));
    CHECK(snd_pcm_sw_params(pcm, sw));
    CHECK(snd_pcm_prepare(pcm));
    tty = open("/dev/tty1", O_WRONLY | O_NOCTTY | O_NONBLOCK);
    printf("{\"event\":\"configured\",\"pid\":%ld,\"library\":\"%s\",\"rate\":%u,\"channels\":2,\"period\":%u,\"buffer\":%u,\"period_wakeup\":%u,\"period_event\":%d,\"source_frames\":%" PRIu64 ",\"source_seconds\":%u,\"mixer_writes\":false}\n", (long)getpid(), snd_asoundlib_version(), RATE, PERIOD, BUFFER, period_wakeup, PERIOD_EVENT, stream_frames(), (unsigned)(stream_frames() / RATE));
    while (written < stream_frames() && !stopped) {
        if (clock_seconds(CLOCK_MONOTONIC_RAW) - started > MAX_SECONDS) { fail("wall_deadline", -ETIMEDOUT); goto done; }
        const size_t n = stream_frames() - written < PERIOD ? (size_t)(stream_frames() - written) : PERIOD;
        bool must_wait = false;
        if (WHOLE_PERIOD_WRITES) {
            const snd_pcm_sframes_t available = snd_pcm_avail(pcm);
            if (available < 0) { fail("snd_pcm_avail", (int)available); goto done; }
            must_wait = (uint64_t)available < n;
        }
        fill(block, written, n);
        const double write_begin = clock_seconds(CLOCK_MONOTONIC_RAW);
        const snd_pcm_sframes_t got = must_wait ? -EAGAIN : snd_pcm_writei(pcm, block, n);
        const double write_elapsed = clock_seconds(CLOCK_MONOTONIC_RAW) - write_begin;
        write_seconds += write_elapsed; if (write_elapsed > write_max) write_max = write_elapsed;
        if (got == -EAGAIN || got == 0) {
            ++waits;
            const double wait_begin = clock_seconds(CLOCK_MONOTONIC_RAW);
            rc = snd_pcm_wait(pcm, WAIT_TIMEOUT_MS);
            const double wait_elapsed = clock_seconds(CLOCK_MONOTONIC_RAW) - wait_begin;
            wait_seconds += wait_elapsed; if (wait_elapsed > wait_max) wait_max = wait_elapsed;
            if (rc == 0) ++wait_timeouts;
            if (rc < 0) { fail("snd_pcm_wait", rc); goto done; }
            if (waits <= WAIT_LOG_LIMIT) printf("{\"event\":\"wait\",\"written\":%" PRIu64 ",\"elapsed_raw_seconds\":%.6f,\"wait_seconds\":%.6f,\"ready\":%d}\n", written, clock_seconds(CLOCK_MONOTONIC_RAW) - started, wait_elapsed, rc);
        } else if (got < 0) {
            fail("snd_pcm_writei", (int)got); goto done;
        } else {
            if ((size_t)got < n) ++partial;
            written += (uint64_t)got;
        }
        const double now = clock_seconds(CLOCK_MONOTONIC_RAW);
        if (now >= next_sample) {
            next_sample = now + 1.0;
            CHECK(snd_pcm_status(pcm, status));
            const snd_pcm_state_t state = snd_pcm_status_get_state(status);
            if (state == SND_PCM_STATE_XRUN) { fail("status_XRUN", -EPIPE); goto done; }
            const snd_pcm_sframes_t delay = snd_pcm_status_get_delay(status);
            const uint64_t queued = delay > 0 ? (uint64_t)delay : 0;
            const uint64_t played = state == SND_PCM_STATE_PREPARED ? 0 : written > queued ? written - queued : 0;
            const unsigned p = phase_at(played);
            if ((int)p != last_phase) {
                last_phase = (int)p;
                const uint64_t remaining = stream_frames() > boundary[p] ? stream_frames() - boundary[p] : 0;
                const unsigned source_seconds = remaining < (uint64_t)phases[p].seconds * RATE ? (unsigned)(remaining / RATE) : phases[p].seconds;
                printf("{\"event\":\"phase\",\"phase\":\"%s\",\"source_seconds\":%u,\"monotonic_raw\":%.6f,\"played_estimate\":%" PRIu64 "}\n", phases[p].name, source_seconds, now, played);
                const double tty_begin = clock_seconds(CLOCK_MONOTONIC_RAW);
                if (tty >= 0) dprintf(tty, "\033[2J\033[HStandalone ALSA audio test\r\n\r\n%s\r\n\r\nNo EmulationStation, SDL or video playback.\r\nKeep volume and controls unchanged.\r\nMenu restores automatically.\r\n", phases[p].name);
                tty_seconds += clock_seconds(CLOCK_MONOTONIC_RAW) - tty_begin;
            }
            printf("{\"event\":\"sample\",\"monotonic_raw\":%.6f,\"written\":%" PRIu64 ",\"delay\":%ld,\"avail\":%lu,\"state\":%d,\"cpu_seconds\":%.6f}\n", now, written, (long)delay, (unsigned long)snd_pcm_status_get_avail(status), (int)state, clock_seconds(CLOCK_PROCESS_CPUTIME_ID) - cpu_started);
        }
    }
    if (stopped) { fail("signal", -EINTR); goto done; }
    double next_drain_sample = 0.0;
    for (;;) {
        rc = snd_pcm_drain(pcm);
        if (rc != 0 && rc != -EAGAIN) { fail("snd_pcm_drain", rc); goto done; }
        /* The hw backend can keep returning EAGAIN after the kernel has
         * reached SETUP. Query state explicitly, including SYNC_PTR fallback. */
        const snd_pcm_state_t drain_state = snd_pcm_state(pcm);
        if (drain_state == SND_PCM_STATE_SETUP) {
            printf("{\"event\":\"drained\",\"elapsed_raw_seconds\":%.6f,\"state\":%d,\"last_drain_return\":%d}\n", clock_seconds(CLOCK_MONOTONIC_RAW) - started, (int)drain_state, rc);
            break;
        }
        if (rc == 0 || drain_state != SND_PCM_STATE_DRAINING) { fail("unexpected_drain_state", -EBADFD); goto done; }
        const double now = clock_seconds(CLOCK_MONOTONIC_RAW);
        if (now >= next_drain_sample) {
            next_drain_sample = now + 1.0;
            CHECK(snd_pcm_status(pcm, status));
            printf("{\"event\":\"drain_sample\",\"elapsed_raw_seconds\":%.6f,\"written\":%" PRIu64 ",\"delay\":%ld,\"avail\":%lu,\"state\":%d}\n", now - started, written, (long)snd_pcm_status_get_delay(status), (unsigned long)snd_pcm_status_get_avail(status), (int)snd_pcm_status_get_state(status));
        }
        if (stopped || clock_seconds(CLOCK_MONOTONIC_RAW) - started > MAX_SECONDS) { fail("drain_deadline", -ETIMEDOUT); goto done; }
        /* Completion can change the poll state; retry drain itself after a bounded sleep. */
        const struct timespec pause = { .tv_sec = 0, .tv_nsec = 10000000 };
        nanosleep(&pause, NULL);
    }
    result = 0;
done:
    if (pcm) { if (result != 0) snd_pcm_drop(pcm); snd_pcm_close(pcm); }
    if (hw) snd_pcm_hw_params_free(hw);
    if (sw) snd_pcm_sw_params_free(sw);
    if (status) snd_pcm_status_free(status);
    if (tty >= 0) close(tty);
    const double elapsed = clock_seconds(CLOCK_MONOTONIC_RAW) - started;
    printf("{\"event\":\"application_end\",\"result\":%d,\"written\":%" PRIu64 ",\"elapsed_raw_seconds\":%.6f,\"cpu_seconds\":%.6f,\"partial_writes\":%" PRIu64 ",\"waits\":%" PRIu64 ",\"wait_timeouts\":%" PRIu64 ",\"wait_timeout_ms\":%d,\"wait_seconds\":%.6f,\"wait_max_seconds\":%.6f,\"write_seconds\":%.6f,\"write_max_seconds\":%.6f,\"tty_seconds\":%.6f,\"xrun_recovery_attempts\":0}\n", result, written, elapsed, clock_seconds(CLOCK_PROCESS_CPUTIME_ID) - cpu_started, partial, waits, wait_timeouts, WAIT_TIMEOUT_MS, wait_seconds, wait_max, write_seconds, write_max, tty_seconds);
    return result;
#undef CHECK
}
int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    if (argc != 2 && argc != 3) { fprintf(stderr, "Use --selftest, --dump NEW_RAW_FILE, or --run\n"); return 2; }
    initialize();
    if (argc == 2 && strcmp(argv[1], "--selftest") == 0) {
        printf("{\"event\":\"selftest\",\"library\":\"%s\",\"frames\":%" PRIu64 ",\"source_seconds\":%u,\"rate\":%u,\"channels\":2,\"period\":%u,\"buffer\":%u}\n", snd_asoundlib_version(), stream_frames(), (unsigned)(stream_frames() / RATE), RATE, PERIOD, BUFFER);
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "--dump") == 0) return dump_reference(argv[2]);
    if (argc != 2 || strcmp(argv[1], "--run") != 0) return 2;
    struct sigaction action;
    memset(&action, 0, sizeof(action)); action.sa_handler = stop_signal; sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, NULL); sigaction(SIGTERM, &action, NULL); sigaction(SIGHUP, &action, NULL);
    return playback();
}
