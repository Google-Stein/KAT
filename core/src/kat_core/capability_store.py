"""Owner-managed capability configuration, outside the model registry."""

from uuid import uuid4

from kat_core.capability_schemas import (
    Capabilities,
    CapabilityFailure,
    Location,
    ReadRoot,
    RootCreate,
)
from kat_core.storage import Store


class CapabilityStore:
    def __init__(self, store: Store) -> None:
        self.store = store

    def configuration(self) -> Capabilities:
        with self.store.transaction() as db:
            weather = db.execute("SELECT weather FROM capabilities WHERE id=1").fetchone()[0]
            roots = [
                ReadRoot(**dict(r)) for r in db.execute("SELECT * FROM read_roots ORDER BY id")
            ]
        return Capabilities(
            weather_location=Location.model_validate_json(weather) if weather else None,
            read_roots=roots,
        )

    def set_weather(self, location: Location | None) -> Capabilities:
        with self.store.transaction() as db:
            db.execute(
                "UPDATE capabilities SET weather=? WHERE id=1",
                (location.model_dump_json() if location else None,),
            )
        self.store.add_audit(
            "weather_configuration_changed", details={"configured": location is not None}
        )
        return self.configuration()

    def add_root(self, value: RootCreate) -> ReadRoot:
        from kat_core.file_access import validate_root

        path = validate_root(value.path)
        root = ReadRoot(id="root-" + uuid4().hex[:24], label=value.label, path=str(path))
        with self.store.transaction() as db:
            if db.execute("SELECT count(*) FROM read_roots").fetchone()[0] >= 12:
                raise CapabilityFailure(
                    "root_limit", "At most 12 read-only folders may be registered."
                )
            if db.execute("SELECT 1 FROM read_roots WHERE path=?", (root.path,)).fetchone():
                raise CapabilityFailure(
                    "root_exists", "This read-only folder is already registered."
                )
            db.execute("INSERT INTO read_roots VALUES (?,?,?)", (root.id, root.label, root.path))
        self.store.add_audit("read_root_added", details={"root_id": root.id})
        return root

    def root(self, root_id: str) -> ReadRoot:
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM read_roots WHERE id=?", (root_id,)).fetchone()
        if row is None:
            raise CapabilityFailure(
                "root_not_found", "This folder is not registered for read-only access."
            )
        return ReadRoot(**dict(row))

    def remove_root(self, root_id: str) -> None:
        with self.store.transaction() as db:
            db.execute("DELETE FROM read_roots WHERE id=?", (root_id,))
        self.store.add_audit("read_root_removed", details={"root_id": root_id})
