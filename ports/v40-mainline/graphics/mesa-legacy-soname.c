/* SPDX-License-Identifier: MIT
 * Some existing programs recorded libMali.so for standard EGL/GLES/GBM APIs.
 * Its dependency graph forwards those APIs to Mesa/GLVND on this kernel only.
 * No proprietary Mali ioctl or nonstandard driver API is implemented here.
 */
int v40_mainline_standard_graphics_compatibility(void) { return 1; }
