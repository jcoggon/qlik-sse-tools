import os
import tempfile


def get_runtime_temp_dir():
    """
    Return the persistent temp directory used by long-running SSE processes.

    CmdStanPy keeps a module-level temp folder for Stan data JSON files. On
    Windows, the normal user temp area can be cleaned while this service is
    still running, leaving CmdStanPy pointing at a folder that no longer exists.
    """
    configured_dir = (
        os.environ.get('QLIK_PY_TOOLS_TEMP_DIR')
        or os.environ.get('CMDSTANPY_TMPDIR')
    )

    if configured_dir:
        return os.path.abspath(os.path.expandvars(os.path.expanduser(configured_dir)))

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'tmp')


def configure_runtime_temp():
    """
    Configure Python and CmdStanPy to use a durable temp directory.

    This is safe to call more than once. Re-calling it before Prophet fits also
    recreates the directory if it was deleted by an external cleanup job.
    """
    temp_dir = get_runtime_temp_dir()
    os.makedirs(temp_dir, exist_ok=True)

    for env_name in ('TMP', 'TEMP', 'TMPDIR', 'CMDSTANPY_TMPDIR'):
        os.environ[env_name] = temp_dir

    # tempfile may have cached the old user temp directory before startup code
    # ran, so update it explicitly for libraries that call tempfile directly.
    tempfile.tempdir = temp_dir

    try:
        import cmdstanpy.utils.filesystem as cmdstan_filesystem
    except Exception:
        return temp_dir

    if hasattr(cmdstan_filesystem, '_TMPDIR'):
        cmdstan_filesystem._TMPDIR = temp_dir

    return temp_dir
