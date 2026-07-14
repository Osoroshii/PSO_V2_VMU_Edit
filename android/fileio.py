"""Platform-abstracted file access: plain filesystem paths on desktop, and
Android's Storage Access Framework (SAF) on Android.

Why this exists: plyer 2.1.0 (and its current `master` branch, as of this
writing) only implements `mode="open"`/`"save"` for its Android file chooser
backend -- `choose_dir()` (`mode="dir"`) hits no branch at all in
`AndroidFileChooser._file_selection_dialog` and silently does nothing. No
exception, no Intent, nothing -- confirmed on a real device (Retroid Pocket
5) by instrumenting the button handler itself and watching adb logcat: the
touch registered, on_release fired, filechooser.choose_dir() was called and
returned without raising, and there was still no Intent-related log line
anywhere in the system log. So Android folder-picking is implemented here
directly via pyjnius (the same Intent.ACTION_OPEN_DOCUMENT_TREE +
onActivityResult pattern plyer's own Android backend uses internally for the
modes it does support), which returns a SAF "tree" URI -- not a filesystem
path, so reading/writing/listing has to go through ContentResolver/
DocumentsContract instead of open()/os.listdir()/shutil.

Everything in this module works given either a folder_ref (desktop: a
directory path string; Android: a tree URI string, e.g.
"content://com.android.externalstorage.documents/tree/XXXX%3AFolder") or a
file_ref (desktop: a file path string; Android: a document URI string) --
callers (vmu_scan.py, session.py) don't need to know which platform they're
on beyond calling these functions.
"""
import os
import shutil

from kivy.utils import platform

IS_ANDROID = platform == "android"

if IS_ANDROID:
    from random import randint

    from android import activity, mActivity
    from jnius import autoclass

    _Intent = autoclass("android.content.Intent")
    _Activity = autoclass("android.app.Activity")
    _DocumentsContract = autoclass("android.provider.DocumentsContract")
    _Document = autoclass("android.provider.DocumentsContract$Document")
    _Uri = autoclass("android.net.Uri")

    _select_code = randint(123456, 654321)
    _pending_callback = None

    def _on_activity_result(request_code, result_code, data):
        global _pending_callback
        if request_code != _select_code:
            return
        cb, _pending_callback = _pending_callback, None
        if cb is None:
            return
        if result_code != _Activity.RESULT_OK or data is None:
            cb(None)
            return
        uri = data.getData()
        try:
            # Without this, access to the picked folder wouldn't survive an
            # app restart -- the grant is otherwise only valid for this
            # activity-result round trip.
            take_flags = data.getFlags() & (
                _Intent.FLAG_GRANT_READ_URI_PERMISSION | _Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            mActivity.getContentResolver().takePersistableUriPermission(uri, take_flags)
        except Exception:
            pass  # best-effort -- worst case this session's access still works
        cb(uri.toString())

    activity.bind(on_activity_result=_on_activity_result)

    def pick_folder(on_selection):
        """on_selection(selection) is called with either [tree_uri_str] (to
        match plyer's choose_dir callback shape -- a list) or None/[]."""
        global _pending_callback

        def wrapped(uri_str):
            on_selection([uri_str] if uri_str else None)

        _pending_callback = wrapped
        intent = _Intent(_Intent.ACTION_OPEN_DOCUMENT_TREE)
        mActivity.startActivityForResult(intent, _select_code)

    def _resolver():
        return mActivity.getContentResolver()

    def _list_tree_children(folder_ref):
        """[(display_name, child_uri_str), ...] for every direct child of
        the picked folder (not recursive, matching how the emulator lays
        out VMU slots flat in one directory)."""
        tree_uri = _Uri.parse(folder_ref)
        root_doc_id = _DocumentsContract.getTreeDocumentId(tree_uri)
        children_uri = _DocumentsContract.buildChildDocumentsUriUsingTree(tree_uri, root_doc_id)
        cursor = _resolver().query(
            children_uri, [_Document.COLUMN_DOCUMENT_ID, _Document.COLUMN_DISPLAY_NAME],
            None, None, None)
        results = []
        if cursor is None:
            return results
        try:
            while cursor.moveToNext():
                doc_id = cursor.getString(0)
                name = cursor.getString(1)
                child_uri = _DocumentsContract.buildDocumentUriUsingTree(tree_uri, doc_id)
                results.append((name, child_uri.toString()))
        finally:
            cursor.close()
        return results

    def list_dir_bin_files(folder_ref):
        results = [(n, u) for n, u in _list_tree_children(folder_ref) if n.lower().endswith(".bin")]
        results.sort(key=lambda t: t[0].lower())
        return results

    def read_bytes(file_ref):
        input_stream = _resolver().openInputStream(_Uri.parse(file_ref))
        chunks = []
        buf = bytearray(65536)
        try:
            while True:
                n = input_stream.read(buf)
                if n == -1:
                    break
                chunks.append(bytes(buf[:n]))
        finally:
            input_stream.close()
        return b"".join(chunks)

    def write_bytes(file_ref, data):
        output_stream = _resolver().openOutputStream(_Uri.parse(file_ref), "wt")
        try:
            output_stream.write(bytearray(data))
            output_stream.flush()
        finally:
            output_stream.close()

    def ensure_backup(folder_ref, file_ref, backup_name):
        """Create backup_name as a sibling of file_ref within folder_ref,
        containing file_ref's current bytes, unless it already exists --
        matches the desktop backup semantics (os.path.exists check, never
        overwritten once made)."""
        if any(n == backup_name for n, _u in _list_tree_children(folder_ref)):
            return
        tree_uri = _Uri.parse(folder_ref)
        root_doc_id = _DocumentsContract.getTreeDocumentId(tree_uri)
        parent_doc_uri = _DocumentsContract.buildDocumentUriUsingTree(tree_uri, root_doc_id)
        new_uri = _DocumentsContract.createDocument(
            _resolver(), parent_doc_uri, "application/octet-stream", backup_name)
        if new_uri is not None:
            write_bytes(new_uri.toString(), read_bytes(file_ref))

else:
    def pick_folder(on_selection):
        from plyer import filechooser
        filechooser.choose_dir(on_selection=on_selection)

    def list_dir_bin_files(folder_ref):
        if not folder_ref or not os.path.isdir(folder_ref):
            return []
        names = sorted(n for n in os.listdir(folder_ref) if n.lower().endswith(".bin"))
        return [(n, os.path.join(folder_ref, n)) for n in names]

    def read_bytes(file_ref):
        with open(file_ref, "rb") as f:
            return f.read()

    def write_bytes(file_ref, data):
        with open(file_ref, "wb") as f:
            f.write(data)

    def ensure_backup(folder_ref, file_ref, backup_name):
        backup_path = file_ref + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(file_ref, backup_path)
