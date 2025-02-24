#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_targetextent
short_description: Manage iSCSI Target-Extent associations
description:
  - Create, update, and delete iSCSI Target-Extent associations (Associated Targets).
version_added: "1.4.3"
options:
  state:
    description:
      - Whether this association should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - ID of an existing target-extent association (for update/delete).
    type: int
  target:
    description:
      - ID of the target (for create/update).
    type: int
  lunid:
    description:
      - LUN ID to assign. If not provided, it is auto-assigned at creation.
    type: int
  extent:
    description:
      - ID of the extent (for create/update).
    type: int
  force:
    description:
      - Force removal if in use, when absent.
    type: bool
    default: false
"""

EXAMPLES = r"""
- name: Create a target-extent association
  iscsi_targetextent:
    state: present
    target: 10
    extent: 20
    lunid: 5

- name: Delete a target-extent association
  iscsi_targetextent:
    state: absent
    id: 15
    force: true
"""

RETURN = r"""
association:
  description:
    - A data structure describing the created or updated target-extent association.
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
            target=dict(type="int"),
            lunid=dict(type="int"),
            extent=dict(type="int"),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]
    assoc_id = params["id"]

    def find_assoc_by_id(aid):
        try:
            recs = mw.call("iscsi.targetextent.query", [["id", "=", aid]])
            return recs[0] if recs else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI targetextent (id={aid}): {e}")

    existing = None
    if assoc_id:
        existing = find_assoc_by_id(assoc_id)

    # absent
    if state == "absent":
        if not assoc_id:
            module.fail_json(
                msg="id is required to delete a target-extent association."
            )
        if not existing:
            result["changed"] = False
            result["msg"] = f"Association {assoc_id} does not exist."
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted association {assoc_id}"
            else:
                try:
                    mw.call("iscsi.targetextent.delete", assoc_id, params["force"])
                    result["msg"] = f"Deleted association {assoc_id}"
                except Exception as e:
                    module.fail_json(msg=f"Error deleting association {assoc_id}: {e}")
            result["changed"] = True
        module.exit_json(**result)

    # present
    if existing:
        # update
        updates = {}
        if params["target"] is not None and existing["target"] != params["target"]:
            updates["target"] = params["target"]
        if params["lunid"] is not None and existing["lunid"] != params["lunid"]:
            updates["lunid"] = params["lunid"]
        if params["extent"] is not None and existing["extent"] != params["extent"]:
            updates["extent"] = params["extent"]

        if not updates:
            result["changed"] = False
            result["association"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would have updated association {assoc_id} with {updates}"
                )
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.targetextent.update", assoc_id, updates)
                    result["association"] = updated
                    result["msg"] = f"Updated association {assoc_id}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating association {assoc_id}: {e}")
    else:
        # create
        if params["target"] is None or params["extent"] is None:
            module.fail_json(
                msg="target and extent are required to create a new association."
            )
        payload = {
            "target": params["target"],
            "extent": params["extent"],
        }
        if params["lunid"] is not None:
            payload["lunid"] = params["lunid"]

        if module.check_mode:
            result["msg"] = f"Would have created new association: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.targetextent.create", payload)
                result["association"] = created
                result["msg"] = "Created new target-extent association"
                result["changed"] = True
            except Exception as e:
                module.fail_json(msg=f"Error creating association: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
