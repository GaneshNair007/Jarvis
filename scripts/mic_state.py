"""Queries the default capture device mute state and master volume via Core Audio (ctypes COM)."""
import ctypes
from ctypes import POINTER, byref, c_float, c_void_p, c_wchar_p

ole32 = ctypes.windll.ole32

CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IMMDevice = "{D666063F-1587-4E43-81F1-B948E807363F}"
IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
IID_IPropertyStore = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"

eCapture = 1
eMultimedia = 1

CLSCTX_ALL = 0x17

REFIID = c_void_p
PROPVARIANT = ctypes.c_byte * 16  # opaque


def guid(s):
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]
    g = GUID()
    ole32.CLSIDFromString(c_wchar_p(s), ctypes.byref(g))
    return g


def main():
    ole32.CoInitializeEx(None, 0)  # COINIT_APARTMENTTHREADED
    enumerator = c_void_p()
    hr = ole32.CoCreateInstance(
        byref(guid(CLSID_MMDeviceEnumerator)),
        None,
        CLSCTX_ALL,
        byref(guid(IID_IMMDeviceEnumerator)),
        byref(enumerator),
    )
    if hr != 0:
        raise RuntimeError(f"CoCreateInstance failed: {hr:#x}")

    # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eCapture, eMultimedia, IMMDevice**)
    dev = c_void_p()
    enum_vtbl = ctypes.cast(enumerator, POINTER(c_void_p))[0]
    enum_funcs = ctypes.cast(enum_vtbl, POINTER(c_void_p))
    get_default = ctypes.WINFUNCTYPE(
        ctypes.c_long, c_void_p, ctypes.c_int, ctypes.c_int, POINTER(c_void_p)
    )(enum_funcs[4])
    hr = get_default(enumerator, eCapture, eMultimedia, byref(dev))
    if hr != 0 or not dev:
        raise RuntimeError(f"GetDefaultAudioEndpoint failed: {hr:#x}")

    # IMMDevice::Activate(IAudioEndpointVolume)
    vol = c_void_p()
    dev_vtbl = ctypes.cast(dev, POINTER(c_void_p))[0]
    dev_funcs = ctypes.cast(dev_vtbl, POINTER(c_void_p))
    activate = ctypes.WINFUNCTYPE(
        ctypes.c_long, c_void_p, c_void_p, ctypes.c_ulong, c_void_p, POINTER(c_void_p)
    )(dev_funcs[3])
    g = guid(IID_IAudioEndpointVolume)
    hr = activate(dev, ctypes.addressof(g), CLSCTX_ALL, None, byref(vol))
    if hr != 0 or not vol:
        raise RuntimeError(f"Activate(IAudioEndpointVolume) failed: {hr:#x}")

    # IAudioEndpointVolume::GetMute -> index 15, GetMasterVolumeLevelScalar -> index 9
    vol_vtbl = ctypes.cast(vol, POINTER(c_void_p))[0]
    vol_funcs = ctypes.cast(vol_vtbl, POINTER(c_void_p))
    get_mute = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(ctypes.c_int))(vol_funcs[15])
    get_master = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(c_float))(vol_funcs[9])

    muted = ctypes.c_int(1)
    hr = get_mute(vol, byref(muted))
    level = c_float(0.0)
    hr2 = get_master(vol, byref(level))

    print(f"default capture device mute: {bool(muted.value)}  (hr={hr:#x})")
    print(f"master volume scalar: {level.value:.3f}  (hr={hr2:#x})")
    print("MIC MUTED" if muted.value else "MIC UNMUTED - volume OK")


if __name__ == "__main__":
    main()
