/* Optional SM64 trial. Generate native code through the ordinary ARM emitter.
 * The local profile contains only guest addresses and fingerprints.
 */
#include "jit-warm-profile.h"

#define V40_WARM_WORDS (MAXBLOCK + 2)
#define V40_WARM_SCAN_LIMIT 4

static unsigned v40_warm_cursor, v40_warm_scans, v40_warm_matches, v40_warm_compiled;
static unsigned v40_warm_vi, v40_warm_completed, v40_warm_jal_changes;
static int v40_warm_enabled;
static unsigned char v40_warm_done[sizeof(v40_warm_profile) / sizeof(*v40_warm_profile)];
static uint64_t v40_warm_peak_ns;

static void v40_warm_init(void)
{
  const char *option = getenv("V40_JIT_WARMUP");
  v40_warm_enabled = option && strcmp(option, "1") == 0 &&
      memcmp(ROM_SETTINGS.MD5, v40_warm_rom_md5, 32) == 0;
  memset(v40_warm_done, 0, sizeof(v40_warm_done));
  v40_warm_cursor = v40_warm_scans = v40_warm_matches = v40_warm_compiled = 0;
  v40_warm_vi = v40_warm_completed = v40_warm_jal_changes = 0;
  v40_warm_cache_wrapped = 0;
  v40_warm_peak_ns = 0;
}

static void v40_warm_dump(void)
{
  if (v40_warm_enabled)
    fprintf(stderr, "V40_JIT_WARM scanned=%u matches=%u compiled=%u peak_ns=%llu wrapped=%d jal_changes=%u\n",
            v40_warm_scans, v40_warm_matches, v40_warm_compiled,
            (unsigned long long)v40_warm_peak_ns, v40_warm_cache_wrapped, v40_warm_jal_changes);
}

static uint64_t v40_warm_fingerprint(const uint32_t *guest_words)
{
  uint64_t hash = UINT64_C(14695981039346656037);
  unsigned i;
  for (i = 0; i < V40_WARM_WORDS; ++i) {
    const uint32_t word = guest_words[i];
    hash = (hash ^ (word >> 24)) * UINT64_C(1099511628211);
    hash = (hash ^ ((word >> 16) & 255)) * UINT64_C(1099511628211);
    hash = (hash ^ ((word >> 8) & 255)) * UINT64_C(1099511628211);
    hash = (hash ^ (word & 255)) * UINT64_C(1099511628211);
  }
  return hash;
}

static int v40_warm_has_entry(uint32_t guest_pc)
{
  const unsigned page = (guest_pc - UINT32_C(0x80000000)) >> 12;
  const struct ll_entry *entry;
  for (entry = jump_in[page]; entry; entry = entry->next)
    if (entry->vaddr == guest_pc && entry->reg_sv_flags == 0)
      return 1;
  for (entry = jump_dirty[page]; entry; entry = entry->next)
    if (entry->vaddr == guest_pc && entry->reg_sv_flags == 0)
      return 1;
  return 0;
}

void v40_jit_warm_on_vi(void)
{
  const unsigned count = sizeof(v40_warm_done);
  uintptr_t host_used, shadow_used;
  uint64_t before, after;
  unsigned scanned = 0, visited = 0;

  if (!v40_warm_enabled || (++v40_warm_vi & 1) || v40_warm_completed == count)
    return;
  host_used = (uintptr_t)out - (uintptr_t)base_addr;
  shadow_used = (uintptr_t)copy - (uintptr_t)shadow;
  /* The VI handler can return to existing generated code. The extra block and
   * its expiry horizon must both stay ahead of every previously emitted block.
   */
  if (!g_dev.ri.rdram.dram || stop || pending_exception || v40_warm_cache_wrapped ||
      using_tlb || stop_after_jal ||
      host_used >= (UINT32_C(1) << (TARGET_SIZE_2 - 1)) - MAX_OUTPUT_BLOCK_SIZE ||
      shadow_used >= sizeof(shadow) - MAXBLOCK * sizeof(uint32_t))
    return;

  before = v40_jit_now(CLOCK_MONOTONIC);
  while (visited < count && scanned < V40_WARM_SCAN_LIMIT) {
    const unsigned slot = v40_warm_cursor;
    const struct v40_warm_entry *entry = &v40_warm_profile[slot];
    const uint32_t pc = entry->pc;
    const uint32_t offset = pc - UINT32_C(0x80000000);
    const size_t length = V40_WARM_WORDS * sizeof(uint32_t);
    unsigned prior_stop;
    v40_warm_cursor = (slot + 1) % count;
    ++visited;
    if (v40_warm_done[slot] || (pc & 3) || offset < 4096 ||
        g_dev.ri.rdram.dram_size < length ||
        offset > g_dev.ri.rdram.dram_size - length ||
        offset > UINT32_C(0x00800000) - length)
      continue;

    if (v40_warm_has_entry(pc)) {
      v40_warm_done[slot] = 1;
      ++v40_warm_completed;
      continue;
    }

    ++scanned;
    ++v40_warm_scans;
    if (v40_warm_fingerprint(g_dev.ri.rdram.dram + offset / 4) != entry->fingerprint)
      continue;

    ++v40_warm_matches;
    v40_warm_done[slot] = 1;
    ++v40_warm_completed;
    prior_stop = stop_after_jal;
    if (v40_recompile_block(pc) == 0 && v40_warm_has_entry(pc))
      ++v40_warm_compiled;
    if (stop_after_jal != prior_stop) {
      ++v40_warm_jal_changes;
      stop_after_jal = prior_stop;
    }
    break;
  }
  after = v40_jit_now(CLOCK_MONOTONIC);
  if (before && after >= before && after - before > v40_warm_peak_ns)
    v40_warm_peak_ns = after - before;
}
