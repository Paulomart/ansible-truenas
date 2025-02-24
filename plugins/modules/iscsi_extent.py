#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_extent
short_description: Manage iSCSI Extents
description:
  - Create, update, and delete iSCSI Extents.
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
      - Extent ID (for update/delete).
    type: int
  name:
    description:
      - Name of the extent.
    type: str
  type:
    description:
      - Whether extent is FILE or DISK.
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
- name: Create a FILE-based iSCSI extent
  iscsi_extent:
    state: present
    name: "my_file_extent"
    type: "FILE"
    path: "/mnt/tank/iscsi_extent.img"
    filesize: 1073741824
    blocksize: 512

- name: Delete iSCSI extent
  iscsi_extent:
    state: absent
    id: 5
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

    # Helper to find an extent by ID
    def find_extent_by_id(eid):
        try:
            res = mw.call("iscsi.extent.query", [["id", "=", eid]])
            return res[0] if res else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI extent (id={eid}): {e}")

    existing = None
    if ext_id:
        existing = find_extent_by_id(ext_id)

    # state=absent
    if state == "absent":
        if not ext_id:
            module.fail_json(msg="id is required to delete an iSCSI extent.")
        if not existing:
            result["changed"] = False
            result["msg"] = f"Extent {ext_id} does not exist."
            module.exit_json(**result)
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted extent {ext_id}"
            else:
                try:
                    mw.call(
                        "iscsi.extent.delete", ext_id, params["remove"], params["force"]
                    )
                    result["msg"] = f"Deleted extent {ext_id}"
                except Exception as e:
                    module.fail_json(msg=f"Error deleting extent {ext_id}: {e}")
            result["changed"] = True
            module.exit_json(**result)

    # state=present
    if existing:
        # Update
        updates = {}
        if params["name"] is not None and existing["name"] != params["name"]:
            updates["name"] = params["name"]
        if params["type"] is not None and existing["type"] != params["type"]:
            updates["type"] = params["type"]
        if params["disk"] is not None and existing["disk"] != params["disk"]:
            updates["disk"] = params["disk"]
        if params["path"] is not None and existing["path"] != params["path"]:
            updates["path"] = params["path"]
        if (
            params["filesize"] is not None
            and existing["filesize"] != params["filesize"]
        ):
            updates["filesize"] = params["filesize"]
        if (
            params["blocksize"] is not None
            and existing["blocksize"] != params["blocksize"]
        ):
            updates["blocksize"] = params["blocksize"]
        if (
            params["pblocksize"] is not None
            and existing["pblocksize"] != params["pblocksize"]
        ):
            updates["pblocksize"] = params["pblocksize"]
        if (
            params["avail_threshold"] is not None
            and existing["avail_threshold"] != params["avail_threshold"]
        ):
            updates["avail_threshold"] = params["avail_threshold"]
        if params["comment"] is not None and existing["comment"] != params["comment"]:
            updates["comment"] = params["comment"]
        if (
            params["insecure_tpc"] is not None
            and existing["insecure_tpc"] != params["insecure_tpc"]
        ):
            updates["insecure_tpc"] = params["insecure_tpc"]
        if params["xen"] is not None and existing["xen"] != params["xen"]:
            updates["xen"] = params["xen"]
        if params["rpm"] is not None and existing["rpm"] != params["rpm"]:
            updates["rpm"] = params["rpm"]
        if params["ro"] is not None and existing["ro"] != params["ro"]:
            updates["ro"] = params["ro"]
        if params["enabled"] is not None and existing["enabled"] != params["enabled"]:
            updates["enabled"] = params["enabled"]

        if not updates:
            result["changed"] = False
            result["extent"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = f"Would have updated extent {ext_id} with {updates}"
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
        # Create
        if not params["name"]:
            module.fail_json(msg="name is required to create an iSCSI extent.")
        if not params["type"]:
            module.fail_json(msg="type is required to create an iSCSI extent.")

        payload = {
            "name": params["name"],
            "type": params["type"],
        }
        # Add optional fields if provided
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
                result["msg"] = "Created new iSCSI extent"
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI extent: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
