"""Automatic file history: every flushed change of a ProjectFile leaves an immutable FileVersion."""

from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session, attributes

from ..models import FileVersion, ProjectFile

MAX_VERSIONS_PER_PATH = 50


def _record(session: Session, file: ProjectFile) -> None:
    if file.version is None:
        file.version = 1
    session.add(FileVersion(project_id=file.project_id, path=file.path, version=file.version,
                            content=file.content or "", source=session.info.get("version_source", "manual")))


@event.listens_for(Session, "before_flush")
def snapshot_files(session: Session, _context, _instances) -> None:
    changed = [obj for obj in session.new if isinstance(obj, ProjectFile)]
    for obj in session.dirty:
        if isinstance(obj, ProjectFile) and attributes.get_history(obj, "content").has_changes():
            changed.append(obj)
    for file in changed:
        _record(session, file)
    with session.no_autoflush:
        for path_key in {(file.project_id, file.path) for file in changed}:
            project_id, path = path_key
            keep = session.scalars(select(FileVersion.version).where(
                FileVersion.project_id == project_id, FileVersion.path == path)
                .order_by(FileVersion.version.desc()).limit(MAX_VERSIONS_PER_PATH - 1)).all()
            # The new snapshot is not flushed yet, so keep one slot free for it.
            if len(keep) == MAX_VERSIONS_PER_PATH - 1:
                session.execute(delete(FileVersion).where(
                    FileVersion.project_id == project_id, FileVersion.path == path,
                    FileVersion.version < min(keep)))


def next_version(session: Session, project_id, path: str) -> int:
    return (session.scalar(select(func.max(FileVersion.version)).where(
        FileVersion.project_id == project_id, FileVersion.path == path)) or 0) + 1
