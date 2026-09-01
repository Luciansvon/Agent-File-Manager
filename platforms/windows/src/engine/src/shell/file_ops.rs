//! Reviewed file mutations through Windows `IFileOperation`.

use std::path::Path;

use anyhow::{bail, Context, Result};
use windows::core::PCWSTR;
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CoUninitialize, CLSCTX_ALL, COINIT_APARTMENTTHREADED,
};
use windows::Win32::UI::Shell::{
    FileOperation, IFileOperation, IShellItem, SHCreateItemFromParsingName, FOF_ALLOWUNDO,
    FOF_NOCONFIRMATION, FOF_NOERRORUI, FOF_SILENT,
};

/// Rename one file inside its current directory. Collision auto-renaming and
/// replacement are deliberately not enabled; an occupied target is an error.
pub fn rename_path(source: &Path, destination: &Path) -> Result<()> {
    use std::os::windows::ffi::OsStrExt;

    if source.parent() != destination.parent() {
        bail!("rename operation must stay in the source directory");
    }
    let new_name = destination
        .file_name()
        .context("rename destination has no filename")?;
    if std::fs::symlink_metadata(crate::util::path_safety::to_extended_length(destination)).is_ok()
    {
        bail!("rename destination already exists");
    }

    let source_wide: Vec<u16> = source
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let name_wide: Vec<u16> = new_name
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();

    unsafe {
        let initialized = CoInitializeEx(None, COINIT_APARTMENTTHREADED).is_ok();
        let result = (|| -> Result<()> {
            let operation: IFileOperation =
                CoCreateInstance(&FileOperation, None, CLSCTX_ALL)
                    .context("CoCreateInstance(IFileOperation)")?;
            operation
                .SetOperationFlags(
                    FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
                )
                .context("SetOperationFlags for rename")?;
            let item: IShellItem =
                SHCreateItemFromParsingName(PCWSTR(source_wide.as_ptr()), None)
                    .context("SHCreateItemFromParsingName for rename")?;
            operation
                .RenameItem(&item, PCWSTR(name_wide.as_ptr()), None)
                .context("queue IFileOperation rename")?;
            operation
                .PerformOperations()
                .context("perform IFileOperation rename")?;
            if operation.GetAnyOperationsAborted()?.as_bool() {
                bail!("Windows aborted the rename operation");
            }
            Ok(())
        })();
        if initialized {
            CoUninitialize();
        }
        result?;
    }

    let source_exists =
        std::fs::symlink_metadata(crate::util::path_safety::to_extended_length(source)).is_ok();
    let destination_exists =
        std::fs::symlink_metadata(crate::util::path_safety::to_extended_length(destination)).is_ok();
    if source_exists || !destination_exists {
        bail!("Windows did not complete the requested rename");
    }
    Ok(())
}

/// Move one reviewed file to an existing destination directory. The caller
/// creates/validates that directory and resolves collisions before entering
/// this function; shell auto-renaming/replacement flags are never enabled.
pub fn move_path(source: &Path, destination: &Path) -> Result<()> {
    use std::os::windows::ffi::OsStrExt;

    let destination_parent = destination
        .parent()
        .context("move destination has no parent directory")?;
    let new_name = destination
        .file_name()
        .context("move destination has no filename")?;
    if source.parent() == Some(destination_parent) {
        return rename_path(source, destination);
    }
    if !destination_parent.is_dir() {
        bail!("move destination directory does not exist");
    }
    if std::fs::symlink_metadata(crate::util::path_safety::to_extended_length(destination)).is_ok()
    {
        bail!("move destination already exists");
    }

    let source_metadata = std::fs::metadata(crate::util::path_safety::to_extended_length(source))
        .context("reading move source metadata")?;
    let source_identity = crate::platform::physical_file_identity(source);
    let source_wide: Vec<u16> = source
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let parent_wide: Vec<u16> = destination_parent
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let name_wide: Vec<u16> = new_name
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();

    unsafe {
        let initialized = CoInitializeEx(None, COINIT_APARTMENTTHREADED).is_ok();
        let result = (|| -> Result<()> {
            let operation: IFileOperation =
                CoCreateInstance(&FileOperation, None, CLSCTX_ALL)
                    .context("CoCreateInstance(IFileOperation)")?;
            operation
                .SetOperationFlags(
                    FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
                )
                .context("SetOperationFlags for move")?;
            let item: IShellItem =
                SHCreateItemFromParsingName(PCWSTR(source_wide.as_ptr()), None)
                    .context("SHCreateItemFromParsingName for move source")?;
            let folder: IShellItem =
                SHCreateItemFromParsingName(PCWSTR(parent_wide.as_ptr()), None)
                    .context("SHCreateItemFromParsingName for move destination")?;
            operation
                .MoveItem(&item, &folder, PCWSTR(name_wide.as_ptr()), None)
                .context("queue IFileOperation move")?;
            operation
                .PerformOperations()
                .context("perform IFileOperation move")?;
            if operation.GetAnyOperationsAborted()?.as_bool() {
                bail!("Windows aborted the move operation");
            }
            Ok(())
        })();
        if initialized {
            CoUninitialize();
        }
        result?;
    }

    let source_exists =
        std::fs::symlink_metadata(crate::util::path_safety::to_extended_length(source)).is_ok();
    let destination_metadata =
        std::fs::metadata(crate::util::path_safety::to_extended_length(destination))
            .context("Windows did not create the requested move destination")?;
    if source_exists || source_metadata.len() != destination_metadata.len() {
        bail!("Windows did not complete the requested move");
    }
    if let (Some(before), Some(after)) = (
        source_identity,
        crate::platform::physical_file_identity(destination),
    ) {
        if before.volume_serial == after.volume_serial && before.file_ref != after.file_ref {
            bail!("move destination identity does not match the reviewed source");
        }
    }
    Ok(())
}
