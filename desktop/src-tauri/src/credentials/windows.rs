//! Windows-owned generic credential, scoped to the current account on this machine.

use super::{CredentialError, CredentialStore, ProviderSecret, MAX_KEY_BYTES};
use std::{ptr, slice};
use windows_sys::Win32::{
    Foundation::{GetLastError, ERROR_CANCELLED, ERROR_NOT_FOUND, HWND},
    Security::Credentials::{
        CredDeleteW, CredFree, CredReadW, CredUIPromptForCredentialsW, CredWriteW, CREDENTIALW,
        CREDUI_FLAGS_ALWAYS_SHOW_UI, CREDUI_FLAGS_DO_NOT_PERSIST, CREDUI_FLAGS_GENERIC_CREDENTIALS,
        CREDUI_FLAGS_KEEP_USERNAME, CREDUI_INFOW, CRED_PERSIST_LOCAL_MACHINE, CRED_TYPE_GENERIC,
    },
};
use zeroize::{Zeroize, Zeroizing};

const TARGET: &str = "KAT/OpenAI";

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}

/// Owns precisely the buffer returned by CredReadW; clear before releasing it.
struct ReadCredential(*mut CREDENTIALW);

impl ReadCredential {
    fn load(target_name: &str) -> Result<Option<Self>, CredentialError> {
        let target = wide(target_name);
        let mut credential = ptr::null_mut();
        // target is NUL terminated; credential is an initialized output pointer.
        let success = unsafe { CredReadW(target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut credential) };
        if success == 0 {
            if unsafe { GetLastError() } == ERROR_NOT_FOUND {
                return Ok(None);
            }
            return Err(CredentialError::Read);
        }
        if credential.is_null() {
            return Err(CredentialError::Read);
        }
        Ok(Some(Self(credential)))
    }

    fn secret(&self) -> Result<ProviderSecret, CredentialError> {
        // CredReadW owns this live allocation until this guard calls CredFree.
        let credential = unsafe { &*self.0 };
        let length = credential.CredentialBlobSize as usize;
        if length == 0 || length > MAX_KEY_BYTES || credential.CredentialBlob.is_null() {
            return Err(CredentialError::Read);
        }
        let bytes = unsafe { slice::from_raw_parts(credential.CredentialBlob, length) };
        let value = std::str::from_utf8(bytes).map_err(|_| CredentialError::Read)?;
        ProviderSecret::validate(value.to_owned()).map_err(|_| CredentialError::Read)
    }
}

impl Drop for ReadCredential {
    fn drop(&mut self) {
        // The size and pointer belong to the allocation returned by Windows.
        unsafe {
            let credential = &*self.0;
            if !credential.CredentialBlob.is_null() && credential.CredentialBlobSize > 0 {
                slice::from_raw_parts_mut(
                    credential.CredentialBlob,
                    credential.CredentialBlobSize as usize,
                )
                .zeroize();
            }
            CredFree(self.0.cast());
        }
    }
}

pub(super) struct WindowsCredentialStore;

impl CredentialStore for WindowsCredentialStore {
    fn supported(&self) -> bool {
        true
    }

    fn contains(&self) -> Result<bool, CredentialError> {
        Ok(ReadCredential::load(TARGET)?.is_some())
    }

    fn read(&self) -> Result<Option<ProviderSecret>, CredentialError> {
        ReadCredential::load(TARGET)?
            .map(|credential| credential.secret())
            .transpose()
    }

    fn write(&self, secret: &ProviderSecret) -> Result<(), CredentialError> {
        write_target(TARGET, secret)
    }

    fn remove(&self) -> Result<bool, CredentialError> {
        remove_target(TARGET)
    }
}

fn write_target(target_name: &str, secret: &ProviderSecret) -> Result<(), CredentialError> {
    let mut target = wide(target_name);
    let mut username = wide("OpenAI");
    let mut blob = Zeroizing::new(secret.0.as_bytes().to_vec());
    let credential = CREDENTIALW {
        Type: CRED_TYPE_GENERIC,
        TargetName: target.as_mut_ptr(),
        CredentialBlobSize: blob.len() as u32,
        CredentialBlob: blob.as_mut_ptr(),
        Persist: CRED_PERSIST_LOCAL_MACHINE,
        UserName: username.as_mut_ptr(),
        ..Default::default()
    };
    // All backing buffers stay alive through this synchronous API call.
    if unsafe { CredWriteW(&credential, 0) } == 0 {
        return Err(CredentialError::Write);
    }
    Ok(())
}

fn remove_target(target_name: &str) -> Result<bool, CredentialError> {
    let target = wide(target_name);
    if unsafe { CredDeleteW(target.as_ptr(), CRED_TYPE_GENERIC, 0) } == 0 {
        if unsafe { GetLastError() } == ERROR_NOT_FOUND {
            return Ok(false);
        }
        return Err(CredentialError::Delete);
    }
    Ok(true)
}

/// Generic password entry, never a Windows account authentication request.
pub(super) fn prompt(parent_window: usize) -> Result<Option<ProviderSecret>, CredentialError> {
    let target = wide(TARGET);
    let caption = wide("KAT — OpenAI API key");
    let message = wide("Paste your OpenAI API key into Password. KAT saves it in Windows Credential Manager for your current account on this computer. This is not your Windows password. Cancel leaves your existing key unchanged.");
    let mut username = vec![0_u16; 128];
    let initial = wide("OpenAI");
    username[..initial.len()].copy_from_slice(&initial);
    let mut password = Zeroizing::new(vec![0_u16; MAX_KEY_BYTES + 1]);
    let mut save = 0;
    let info = CREDUI_INFOW {
        cbSize: std::mem::size_of::<CREDUI_INFOW>() as u32,
        hwndParent: parent_window as HWND,
        pszMessageText: message.as_ptr(),
        pszCaptionText: caption.as_ptr(),
        ..Default::default()
    };
    // Windows writes only within the provided buffers. DO_NOT_PERSIST prevents
    // the dialog itself from saving; persistence happens only after validation.
    let result = unsafe {
        CredUIPromptForCredentialsW(
            &info,
            target.as_ptr(),
            ptr::null(),
            0,
            username.as_mut_ptr(),
            username.len() as u32,
            password.as_mut_ptr(),
            password.len() as u32,
            &mut save,
            CREDUI_FLAGS_GENERIC_CREDENTIALS
                | CREDUI_FLAGS_ALWAYS_SHOW_UI
                | CREDUI_FLAGS_DO_NOT_PERSIST
                | CREDUI_FLAGS_KEEP_USERNAME,
        )
    };
    if result == ERROR_CANCELLED {
        return Ok(None);
    }
    if result != 0 {
        return Err(CredentialError::Prompt);
    }
    let length = password
        .iter()
        .position(|value| *value == 0)
        .ok_or(CredentialError::InvalidKey)?;
    let value = String::from_utf16(&password[..length]).map_err(|_| CredentialError::InvalidKey)?;
    ProviderSecret::validate(value).map(Some)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TestCredential(String);

    impl Drop for TestCredential {
        fn drop(&mut self) {
            let _ = remove_target(&self.0);
        }
    }

    /// Runs on Windows CI, touches only a unique synthetic current-user entry.
    #[test]
    fn windows_store_roundtrip_replace_and_remove() {
        let target = TestCredential(format!(
            "KAT/Tests/OpenAI/{}-{}",
            std::process::id(),
            crate::new_token().unwrap()
        ));
        assert_ne!(target.0, TARGET);
        assert!(ReadCredential::load(&target.0).unwrap().is_none());
        let first =
            ProviderSecret::validate("sk-proj-test_fixture_only_first_1234".into()).unwrap();
        write_target(&target.0, &first).unwrap();
        let read = ReadCredential::load(&target.0)
            .unwrap()
            .unwrap()
            .secret()
            .unwrap();
        assert!(read.0.as_str() == first.0.as_str());
        let replacement =
            ProviderSecret::validate("sk-proj-test_fixture_only_replace_5678".into()).unwrap();
        write_target(&target.0, &replacement).unwrap();
        let read = ReadCredential::load(&target.0)
            .unwrap()
            .unwrap()
            .secret()
            .unwrap();
        assert!(read.0.as_str() == replacement.0.as_str());
        assert!(remove_target(&target.0).unwrap());
        assert!(ReadCredential::load(&target.0).unwrap().is_none());
        assert!(!remove_target(&target.0).unwrap());
    }
}
