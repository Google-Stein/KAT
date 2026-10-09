//! Native owner folder selection, never invoked by a model tool.

#[cfg(windows)]
pub fn pick_folder(parent: usize) -> Result<Option<String>, String> {
    use windows_sys::Win32::System::Com::{
        CoInitializeEx, CoTaskMemFree, CoUninitialize, COINIT_APARTMENTTHREADED,
    };
    use windows_sys::Win32::UI::Shell::{SHBrowseForFolderW, SHGetPathFromIDListW, BROWSEINFOW};
    unsafe {
        let status = CoInitializeEx(std::ptr::null(), COINIT_APARTMENTTHREADED as u32);
        if status < 0 {
            return Err("Windows folder selection is unavailable.".into());
        }
        let title: Vec<u16> =
            "Choose a folder KAT may list. Reading content still requires approval."
                .encode_utf16()
                .chain(Some(0))
                .collect();
        let info = BROWSEINFOW {
            hwndOwner: parent as _,
            lpszTitle: title.as_ptr(),
            ulFlags: 0x2051, // Filesystem, edit box, modern dialog, no new-folder action.
            ..std::mem::zeroed()
        };
        let item = SHBrowseForFolderW(&info);
        let result = if item.is_null() {
            Ok(None)
        } else {
            let mut path = [0u16; 260];
            let available = SHGetPathFromIDListW(item, path.as_mut_ptr());
            CoTaskMemFree(item.cast());
            if available == 0 {
                Err("Select an ordinary local folder.".into())
            } else {
                let length = path.iter().position(|v| *v == 0).unwrap_or(path.len());
                Ok(Some(String::from_utf16_lossy(&path[..length])))
            }
        };
        CoUninitialize();
        result
    }
}

#[cfg(not(windows))]
pub fn pick_folder(_parent: usize) -> Result<Option<String>, String> {
    Err("Native folder selection is supported on Windows.".into())
}
