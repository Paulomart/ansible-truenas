#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_target
short_description: Manage iSCSI Targets (by id or by unique name)
description:
  - Create, update, and delete iSCSI Targets.
  - If C(id) is not provided, the module attempts to find an existing target by its unique C(name).
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the target should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - Numeric ID of the target (for update/delete).
      - If not set, the module looks up by C(name).
    type: int
  name:
    description:
      - iSCSI target name (often an IQN, e.g. iqn.2005-10.org.freenas.ctl:mytarget) must be unique.
    type: str
  alias:
    description:
      - Optional alias.
    type: str
  mode:
    description:
      - iSCSI, FC, or BOTH.
    type: str
    choices: [ ISCSI, FC, BOTH ]
  groups:
    description:
      - List of group dictionaries: {portal: <id>, initiator: <id>, authmethod: <CHAP|NONE|...>, auth: <id>}
    type: list
    elements: dict
"""

EXAMPLES = r"""
- name: Create or update an iSCSI target by unique name
  iscsi_target:
    state: present
    name: "iqn.2005-10.org.freenas.ctl:mytarget"
    alias: "my_alias"
    mode: "ISCSI"
    groups:
      - portal: 1
        initiator: 2
        authmethod: "CHAP"
        auth: 3

- name: Delete a target by name
  iscsi_target:
    state: absent
    name: "iqn.2005-10.org.freenas.ctl:mytarget"

- name: Delete a target by ID
  iscsi_target:
    state: absent
    id: 10
"""

RETURN = r"""
target:
  description:
    - A data structure describing the created or updated iSCSI target.
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
            alias=dict(type="str"),
            mode=dict(type="str", choices=["ISCSI", "FC", "BOTH"]),
            groups=dict(type="list", elements="dict"),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    p = module.params
    state = p["state"]
    tid = p["id"]
    name = p["name"]

    # gather all targets for name-based lookup
    try:
        all_targets = mw.call("iscsi.target.query")
    except Exception as e:
        module.fail_json(msg=f"Error listing iSCSI targets: {e}")

    def find_target_by_id(ident):
        for t in all_targets:
            if t["id"] == ident:
                return t
        return None

    def find_targets_by_name(n):
        matches = []
        for t in all_targets:
            if (t["name"] or "") == (n or ""):
                matches.append(t)
        return matches

    # -------------------------------------------------------------
    # state=absent
    # -------------------------------------------------------------
    if state == "absent":
        existing = None
        if tid is not None:
            existing = find_target_by_id(tid)
        elif name:
            matches = find_targets_by_name(name)
            if len(matches) > 1:
                module.fail_json(
                    msg=f"Multiple iSCSI targets found with name='{name}'. Provide 'id' to disambiguate."
                )
            elif len(matches) == 1:
                existing = matches[0]

        if not existing:
            result["changed"] = False
            result["msg"] = "Target not found; nothing to delete."
            module.exit_json(**result)
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would delete iSCSI target id={existing['id']} name={existing['name']}"
                )
            else:
                try:
                    mw.call("iscsi.target.delete", existing["id"], {"force": False})
                    result["msg"] = (
                        f"Deleted iSCSI target {existing['id']} name={existing['name']}"
                    )
                except Exception as e:
                    module.fail_json(msg=f"Error deleting target {existing['id']}: {e}")
            result["changed"] = True
            module.exit_json(**result)

    # -------------------------------------------------------------
    # state=present
    # -------------------------------------------------------------
    existing = None
    if tid is not None:
        existing = find_target_by_id(tid)
    else:
        # lookup by name
        if not name:
            module.fail_json(msg="Must provide 'id' or 'name' to manage iSCSI target.")
        matches = find_targets_by_name(name)
        if len(matches) > 1:
            module.fail_json(
                msg=f"Multiple iSCSI targets found with name='{name}'. Provide 'id' instead."
            )
        elif len(matches) == 1:
            existing = matches[0]

    if existing:
        # update
        tid = existing["id"]
        updates = {}
        if p["name"] is not None and existing.get("name") != p["name"]:
            updates["name"] = p["name"]
        if p["alias"] is not None and existing.get("alias") != p["alias"]:
            updates["alias"] = p["alias"]
        if p["mode"] is not None and existing.get("mode") != p["mode"]:
            updates["mode"] = p["mode"]
        if p["groups"] is not None and existing.get("groups") != p["groups"]:
            updates["groups"] = p["groups"]

        if not updates:
            result["changed"] = False
            result["target"] = existing
            result["msg"] = f"No changes needed for target id={tid}"
        else:
            if module.check_mode:
                result["msg"] = f"Would update iSCSI target {tid} with {updates}"
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.target.update", tid, updates)
                    result["target"] = updated
                    result["msg"] = f"Updated iSCSI target id={tid}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating target {tid}: {e}")
    else:
        # create new
        if not name:
            module.fail_json(
                msg="iSCSI target 'name' is required when creating a new target."
            )
        payload = {"name": name}
        if p["alias"] is not None:
            payload["alias"] = p["alias"]
        if p["mode"] is not None:
            payload["mode"] = p["mode"]
        if p["groups"] is not None:
            payload["groups"] = p["groups"]

        if module.check_mode:
            result["msg"] = f"Would create new iSCSI target: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.target.create", payload)
                result["target"] = created
                result["msg"] = f"Created new iSCSI target with name='{name}'"
                result["changed"] = True
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI target: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
