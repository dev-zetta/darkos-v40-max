// SPDX-License-Identifier: MIT
/* Bounded read-only PX30 VOP control snapshot using aligned volatile 32-bit loads. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define VOP_BASE UINT64_C(0xff460000)
#define MAP_BYTES 4096U
struct reg { unsigned offset; const char *name; };
/* No IRQ/status/clear registers, LUT ports, or arbitrary address arguments. */
static const struct reg registers[] = {
    {0x004,"VERSION"}, {0x008,"DSP_BG"},
    {0x010,"SYS_CTRL0"}, {0x014,"SYS_CTRL1"}, {0x018,"SYS_CTRL2"},
    {0x020,"DSP_CTRL0"}, {0x028,"DSP_CTRL2"},
    {0x050,"WIN0_CTRL0"}, {0x054,"WIN0_CTRL1"}, {0x058,"WIN0_COLOR_KEY"},
    {0x05c,"WIN0_VIR"}, {0x060,"WIN0_YRGB_MST0"},
    {0x068,"WIN0_ACT_INFO"}, {0x06c,"WIN0_DSP_INFO"}, {0x070,"WIN0_DSP_ST"},
    {0x074,"WIN0_SCL_FACTOR_YRGB"}, {0x080,"WIN0_ALPHA_CTRL"},
    {0x090,"WIN1_CTRL0"}, {0x0bc,"WIN1_ALPHA_CTRL"},
    {0x100,"DSP_HTOTAL_HS_END"}, {0x104,"DSP_HACT_ST_END"},
    {0x108,"DSP_VTOTAL_VS_END"}, {0x10c,"DSP_VACT_ST_END"},
    {0x160,"BCSH_CTRL"}, {0x164,"BCSH_COL_BAR"}, {0x168,"BCSH_BCS"}, {0x16c,"BCSH_H"},
    {0x190,"WIN2_CTRL0"}, {0x1bc,"WIN2_ALPHA_CTRL"}, {0x1f4,"BLANKING_VALUE"},
    {0x200,"CABC_CTRL0"}, {0x204,"CABC_CTRL1"}, {0x208,"CABC_CTRL2"}, {0x20c,"CABC_CTRL3"},
    {0x240,"AFBCD0_CTRL"},
};

/* Synopsys DSI control/timing/status registers; no FIFO or IRQ read ports. */
static const struct reg dsi_registers[] = {
    {0x000,"VERSION"}, {0x004,"PWR_UP"}, {0x00c,"DPI_VCID"},
    {0x010,"DPI_COLOR_CODING"}, {0x014,"DPI_CFG_POL"}, {0x02c,"PCKHDL_CFG"},
    {0x034,"MODE_CFG"}, {0x038,"VID_MODE_CFG"}, {0x03c,"VID_PKT_SIZE"},
    {0x048,"VID_HSA_TIME"}, {0x04c,"VID_HBP_TIME"}, {0x050,"VID_HLINE_TIME"},
    {0x054,"VID_VSA_LINES"}, {0x058,"VID_VBP_LINES"}, {0x05c,"VID_VFP_LINES"},
    {0x060,"VID_VACTIVE_LINES"}, {0x068,"CMD_MODE_CFG"}, {0x094,"LPCLK_CTRL"},
    {0x0b0,"PHY_STATUS"},
};

/* Keep separate so the emitted AArch64 LDR W instruction can be audited. */
__attribute__((noinline)) static uint32_t read_register(const volatile uint32_t *page, unsigned offset)
{
    return page[offset / sizeof(uint32_t)];
}

static int authorized_target(void)
{
    char marker[64] = {0};
    FILE *file = fopen("/etc/v40-test-card", "r");
    if (!file) return 0;
    int matched = fgets(marker, sizeof(marker), file) &&
        !strcmp(marker, "6a600c53-e187-4865-898b-c1651c60e5db\n");
    fclose(file);
    return matched && geteuid() == 0;
}

int main(int argc, char **argv)
{
    int synthetic = argc == 2 && !strcmp(argv[1], "--self-test");
    int fd = -1;
    void *mapping, *dsi_mapping;
    uint32_t fixture[MAP_BYTES / sizeof(uint32_t)];
    uint32_t dsi_fixture[MAP_BYTES / sizeof(uint32_t)];
    if (!synthetic && argc != 1) { fprintf(stderr, "Usage: %s [--self-test]\n", argv[0]); return 2; }
    if (synthetic) {
        for (unsigned i = 0; i < sizeof(fixture) / sizeof(fixture[0]); ++i)
            fixture[i] = UINT32_C(0xa5a50000) ^ (i * 4U);
        for (unsigned i = 0; i < sizeof(dsi_fixture) / sizeof(dsi_fixture[0]); ++i)
            dsi_fixture[i] = UINT32_C(0x5a5a0000) ^ (i * 4U);
        mapping = fixture;
        dsi_mapping = dsi_fixture;
    } else {
        if (!authorized_target()) { fprintf(stderr, "Requires root on the marked V40 test card\n"); return 1; }
        fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
        if (fd < 0) { perror("open /dev/mem read-only"); return 1; }
        mapping = mmap(NULL, MAP_BYTES, PROT_READ, MAP_SHARED, fd, VOP_BASE);
        if (mapping == MAP_FAILED) { perror("mmap VOP read-only"); close(fd); return 1; }
        dsi_mapping = mmap(NULL, MAP_BYTES, PROT_READ, MAP_SHARED, fd, UINT64_C(0xff450000));
        if (dsi_mapping == MAP_FAILED) { perror("mmap DSI read-only"); munmap(mapping, MAP_BYTES); close(fd); return 1; }
    }
    printf("{\"synthetic\":%s,\"base\":\"0xff460000\",\"access\":\"aligned volatile uint32 read only\",\"registers\":[\n", synthetic ? "true" : "false");
    for (unsigned i = 0; i < sizeof(registers) / sizeof(registers[0]); ++i) {
        uint32_t value = read_register(mapping, registers[i].offset);
        printf("%s{\"offset\":\"0x%03x\",\"name\":\"%s\",\"value\":\"0x%08x\"}",
               i ? ",\n" : "", registers[i].offset, registers[i].name, value);
    }
    puts("\n],\"dsi_base\":\"0xff450000\",\"dsi_registers\":[");
    for (unsigned i = 0; i < sizeof(dsi_registers) / sizeof(dsi_registers[0]); ++i) {
        uint32_t value = read_register(dsi_mapping, dsi_registers[i].offset);
        printf("%s{\"offset\":\"0x%03x\",\"name\":\"%s\",\"value\":\"0x%08x\"}",
               i ? ",\n" : "", dsi_registers[i].offset, dsi_registers[i].name, value);
    }
    puts("\n]}");
    if (!synthetic) { munmap(mapping, MAP_BYTES); munmap(dsi_mapping, MAP_BYTES); close(fd); }
    return 0;
}
