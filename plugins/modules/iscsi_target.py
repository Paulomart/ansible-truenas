#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_target
short_description: Manage iSCSI Targets
description:
  - Create, manage, and delete iSCSI Targets. Also supports query.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the target should exist, not exist, or be queried.
    type: str
    choices: [ absent, present, query ]
    default: present
  id:
    description:
      - ID of the target (for update/delete/query).
    type: int
  name:
    description:
      - iSCSI target name (often an IQN).
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
- name: Create an iSCSI target
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

- name: Query target
  iscsi_target:
    state: query
    id: 10

- name: Delete target
  iscsi_target:
    state: absent
    id: 10
"""

RETURN = r"""
target:
  description:
    - A data structure describing the iSCSI target (created/updated/queried).
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(
                type="str", choices=["absent", "present", "query"], default="present"
            ),
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

    params = module.params
    state = params["state"]
    tid = params["id"]

    def find_target_by_id(tid):
        try:
            recs = mw.call("iscsi.target.query", [["id", "=", tid]])
            return recs[0] if recs else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI target (id={tid}): {e}")

    existing = None
    if tid:
        existing = find_target_by_id(tid)

    # query
    if state == "query":
        if not tid:
            module.fail_json(msg="id is required to query an iSCSI target.")
        if existing:
            result["target"] = existing
            module.exit_json(**result)
        else:
            module.fail_json(msg=f"No iSCSI target found with id={tid}")

    # absent
    if state == "absent":
        if not tid:
            module.fail_json(msg="id is required to delete an iSCSI target.")
        if not existing:
            result["changed"] = False
            result["msg"] = f"Target {tid} does not exist."
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted target {tid}"
            else:
                try:
                    mw.call("iscsi.target.delete", tid, {"force": False})
                    result["msg"] = f"Deleted iSCSI target {tid}"
                except Exception as e:
                    module.fail_json(msg=f"Error deleting target {tid}: {e}")
            result["changed"] = True
        module.exit_json(**result)

    # present
    if existing:
        # update
        updates = {}
        if params["name"] is not None and existing.get("name") != params["name"]:
            updates["name"] = params["name"]
        if params["alias"] is not None and existing.get("alias") != params["alias"]:
            updates["alias"] = params["alias"]
        if params["mode"] is not None and existing.get("mode") != params["mode"]:
            updates["mode"] = params["mode"]
        if params["groups"] is not None and existing.get("groups") != params["groups"]:
            updates["groups"] = params["groups"]

        if not updates:
            result["changed"] = False
            result["target"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = f"Would have updated target {tid} with {updates}"
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.target.update", tid, updates)
                    result["target"] = updated
                    result["msg"] = f"Updated iSCSI target {tid}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating target {tid}: {e}")
    else:
        # create
        if not params["name"]:
            module.fail_json(msg="name is required to create an iSCSI target.")
        payload = {"name": params["name"]}
        if params["alias"] is not None:
            payload["alias"] = params["alias"]
        if params["mode"] is not None:
            payload["mode"] = params["mode"]
        if params["groups"] is not None:
            payload["groups"] = params["groups"]

        if module.check_mode:
            result["msg"] = f"Would have created new iSCSI target: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.target.create", payload)
                result["target"] = created
                result["msg"] = "Created new iSCSI target"
                result["changed"] = True
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI target: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
