#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_extent
short_description: Manage iSCSI Extents (with name-based idempotency)
description:
  - Create, update, and delete iSCSI Extents.
  - If C(id) is not provided, the module tries to find an existing extent by matching C(name).
  - If exactly one matching extent is found, it will be updated.
  - If none are found, it will be created.
  - If multiple matches are found, the module fails to avoid ambiguity.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the extent should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - Numeric ID of an existing iSCSI extent (for update/delete).
      - If not provided, we search by C(name) instead.
    type: int
  name:
    description:
      - Name of the extent (must be unique).
      - Used to look up an existing extent if C(id) is not provided.
    type: str
  type:
    description:
      - Whether the extent is FILE or DISK.
    type: str
    choices: [ FILE, DISK ]
  disk:
    description:
      - For DISK type, the zvol or disk path to use.
    type: str
  path:
    description:
      - For FILE type, the file path to use.
    type: str
  filesize:
    description:
      - For FILE type, size in bytes (multiple of blocksize if not zero).
    type: int
  blocksize:
    description:
      - Logical block size in bytes.
    type: int
  pblocksize:
    description:
      - Use physical block size reporting.
    type: bool
  avail_threshold:
    description:
      - Alert threshold for free bytes.
    type: int
  comment:
    description:
      - Comment for the extent.
    type: str
  insecure_tpc:
    description:
      - Enable initiators to bypass normal access control for xcopy, etc.
    type: bool
  xen:
    description:
      - If true, Xen is used as an iSCSI initiator.
    type: bool
  rpm:
    description:
      - SCSI reported RPM.
    type: str
    choices: [ UNKNOWN, SSD, '5400', '7200', '10000', '15000' ]
  ro:
    description:
      - Read-only extent.
    type: bool
  enabled:
    description:
      - If false, the extent is disabled.
    type: bool
  remove:
    description:
      - If FILE-based extent, remove the file from disk when absent.
    type: bool
    default: false
  force:
    description:
      - Force removal even if in use, when absent.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Create or update a DISK-based iSCSI extent by name
  iscsi_extent:
    state: present
    name: test-extent
    type: DISK
    disk: zvol/test-expansion/test-iscsi

- name: Delete an extent by name
  iscsi_extent:
    state: absent
    name: test-extent
    remove: true

- name: Delete an extent by ID
  iscsi_extent:
    state: absent
    id: 15
    remove: true
"""

RETURN = r"""
extent:
  description:
    - A data structure describing the created or updated iSCSI Extent.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(type="str", choices=["absent", "present"], default="present"),
            id=dict(type="int"),
            name=dict(type="str"),
            type=dict(type="str", choices=["FILE", "DISK"]),
            disk=dict(type="str"),
            path=dict(type="str"),
            filesize=dict(type="int"),
            blocksize=dict(type="int"),
            pblocksize=dict(type="bool"),
            avail_threshold=dict(type="int"),
            comment=dict(type="str"),
            insecure_tpc=dict(type="bool"),
            xen=dict(type="bool"),
            rpm=dict(
                type="str", choices=["UNKNOWN", "SSD", "5400", "7200", "10000", "15000"]
            ),
            ro=dict(type="bool"),
            enabled=dict(type="bool"),
            remove=dict(type="bool", default=False),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]
    ext_id = params["id"]
    name = (
        params["name"].strip() if params["name"] else None
    )  # strip() to remove trailing spaces

    # -------------------------------------------------------------------
    # Fetch all extents in one go, so we can debug/log them if needed.
    # -------------------------------------------------------------------
    try:
        all_extents = mw.call("iscsi.extent.query")
    except Exception as e:
        module.fail_json(msg=f"Error listing all iSCSI extents: {e}")

    # Debug: Uncomment to see what we discovered
    # module.fail_json(msg=f"Debug: all_extents={all_extents}")

    # Helper: find an extent by numeric ID
    def find_by_id(eid, extents):
        for e in extents:
            if e["id"] == eid:
                return e
        return None

    # Helper: find extents by name (exact match, ignoring leading/trailing whitespace)
    def find_by_name(ext_name, extents):
        matches = []
        for e in extents:
            # Also strip stored name in case of trailing spaces in TrueNAS
            stored_name = e["name"].strip() if e["name"] else None
            if stored_name == ext_name:
                matches.append(e)
        return matches

    # -------------------------------------------------------------------
    # state=absent
    # -------------------------------------------------------------------
    if state == "absent":
        # We can identify the extent either by ID or by name
        existing = None
        if ext_id is not None:
            existing = find_by_id(ext_id, all_extents)
        elif name:
            matches = find_by_name(name, all_extents)
            if len(matches) > 1:
                module.fail_json(
                    msg=(
                        f"Multiple iSCSI extents found with name '{name}'. "
                        f"Cannot safely delete. Provide 'id' instead."
                    )
                )
            elif len(matches) == 1:
                existing = matches[0]
            else:
                existing = None

        if not existing:
            result["changed"] = False
            result["msg"] = "iSCSI extent does not exist."
            module.exit_json(**result)
        else:
            # Perform deletion
            if module.check_mode:
                result["msg"] = (
                    f"Would have deleted iSCSI extent {existing['id']} (name='{existing['name']}')"
                )
            else:
                try:
                    mw.call(
                        "iscsi.extent.delete",
                        existing["id"],
                        params["remove"],
                        params["force"],
                    )
                    result["msg"] = (
                        f"Deleted iSCSI extent {existing['id']} (name='{existing['name']}')"
                    )
                except Exception as e:
                    module.fail_json(msg=f"Error deleting extent {existing['id']}: {e}")
            result["changed"] = True
            module.exit_json(**result)

    # -------------------------------------------------------------------
    # state=present (create or update)
    # -------------------------------------------------------------------
    existing = None
    if ext_id is not None:
        # Find by ID explicitly
        existing = find_by_id(ext_id, all_extents)
    else:
        # If no ID given, attempt to find by name
        if not name:
            module.fail_json(
                msg="Must provide either 'id' or 'name' to manage an iSCSI extent (state=present)."
            )

        matches = find_by_name(name, all_extents)
        if len(matches) > 1:
            module.fail_json(
                msg=(
                    f"Multiple iSCSI extents found with name '{name}'. "
                    "Cannot safely manage. Provide 'id' instead."
                )
            )
        elif len(matches) == 1:
            existing = matches[0]

    # If we found an existing extent, we update it
    if existing:
        ext_id = existing["id"]
        updates = {}

        # Shorthand function to compare a field in 'existing' with a param
        def maybe_update(key):
            param_val = params[key]
            if param_val is not None and existing.get(key) != param_val:
                updates[key] = param_val

        # Compare each field
        maybe_update("name")
        maybe_update("type")
        maybe_update("disk")
        maybe_update("path")
        maybe_update("filesize")
        maybe_update("blocksize")
        maybe_update("pblocksize")
        maybe_update("avail_threshold")
        maybe_update("comment")
        maybe_update("insecure_tpc")
        maybe_update("xen")
        maybe_update("rpm")
        maybe_update("ro")
        maybe_update("enabled")

        if not updates:
            result["changed"] = False
            result["extent"] = existing
            result["msg"] = f"Extent {ext_id} is already up-to-date."
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would have updated iSCSI extent {ext_id} with {updates}"
                )
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.extent.update", ext_id, updates)
                    result["extent"] = updated
                    result["changed"] = True
                    result["msg"] = f"Updated iSCSI extent {ext_id}"
                except Exception as e:
                    module.fail_json(msg=f"Error updating extent {ext_id}: {e}")

    else:
        # No existing extent found => create new
        if not name:
            module.fail_json(
                msg="name is required to create a new iSCSI extent (unless 'id' is given)."
            )
        if not params["type"]:
            module.fail_json(msg="'type' is required to create a new iSCSI extent.")

        payload = {
            "name": name,
            "type": params["type"],
        }

        for field in [
            "disk",
            "path",
            "filesize",
            "blocksize",
            "pblocksize",
            "avail_threshold",
            "comment",
            "insecure_tpc",
            "xen",
            "rpm",
            "ro",
            "enabled",
        ]:
            if params[field] is not None:
                payload[field] = params[field]

        if module.check_mode:
            result["msg"] = f"Would have created new iSCSI extent: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.extent.create", payload)
                result["extent"] = created
                result["changed"] = True
                result["msg"] = f"Created new iSCSI extent '{name}'"
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI extent: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
