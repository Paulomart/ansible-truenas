#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_target
short_description: Manage iSCSI Targets (by id or by unique name)
description:
  - Create, update, and delete iSCSI Targets.
  - If C(id) is not provided, the module attempts to find an existing target by its unique C(name).
  - Supports a deep compare for C(groups) to detect changes even if the lists are in different order.
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
      - iSCSI target name (often an IQN, e.g. C(iqn.2005-10.org.freenas.ctl:mytarget)), must be unique.
      - Used for name-based lookups if C(id) is not provided.
    type: str
  alias:
    description:
      - Optional alias for the target.
    type: str
  mode:
    description:
      - iSCSI, FC, or BOTH.
    type: str
    choices: [ ISCSI, FC, BOTH ]
  groups:
    description:
      - List of group dictionaries that define how this target is associated with portals, initiators,
        and iSCSI auth records.
      - When provided, this list is compared to the existing groups in a way that ignores the order
        of items and keys.
      - If the existing groups differ in any way from the desired configuration, the module updates
        them. If you do not specify C(groups), the existing groups remain unchanged.
    type: list
    elements: dict
    suboptions:
      portal:
        description:
          - The numeric ID of an existing iSCSI portal resource.
            E.g., if a portal was created with ID=1, set C(portal: 1).
        type: int
      initiator:
        description:
          - The numeric ID of an existing iSCSI initiator resource.
            E.g., if an initiator was created with ID=2, set C(initiator: 2).
        type: int
      authmethod:
        description:
          - The authentication method to use for this group.
        type: str
        choices: [ NONE, CHAP, CHAP_MUTUAL ]
      auth:
        description:
          - The numeric ID of an iSCSI auth record (CHAP credentials) if needed.
        type: int
      # Other optional keys may exist in the system, but these are the most common ones.
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
            groups=dict(
                type="list",
                elements="dict",
                options=dict(
                    portal=dict(type="int"),
                    initiator=dict(type="int"),
                    authmethod=dict(
                        type="str", choices=["NONE", "CHAP", "CHAP_MUTUAL"]
                    ),
                    auth=dict(type="int"),
                    # You could add more fields here if your system supports them
                ),
            ),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    p = module.params
    state = p["state"]
    tid = p["id"]
    name = p["name"]

    # Retrieve all targets to enable name-based lookup
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

    # ----------------------------------------------------------------
    # Helper: normalize groups for a deep-compare ignoring ordering
    # ----------------------------------------------------------------
    def normalize_groups(grp_list):
        """
        Returns a list of tuples, where each tuple is a sorted version of the dict.
        The overall list is also sorted, so differences in order won't matter.
        """
        if not grp_list:
            return []
        normalized = []
        for item in grp_list:
            # Convert item (dict) -> sorted tuple of (key, value) pairs
            sorted_items = tuple(sorted(item.items()))
            normalized.append(sorted_items)
        # sort the list of tuples so ordering among groups won't matter
        normalized.sort()
        return normalized

    # ----------------------------------------------------------------
    # state=absent
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # state=present
    # ----------------------------------------------------------------
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
        # Update the existing target
        updates = {}
        if p["name"] is not None and existing.get("name") != p["name"]:
            updates["name"] = p["name"]
        if p["alias"] is not None and existing.get("alias") != p["alias"]:
            updates["alias"] = p["alias"]
        if p["mode"] is not None and existing.get("mode") != p["mode"]:
            updates["mode"] = p["mode"]

        # Compare groups with a deep compare ignoring ordering
        if p["groups"] is not None:
            existing_groups_norm = normalize_groups(existing.get("groups"))
            desired_groups_norm = normalize_groups(p["groups"])
            if existing_groups_norm != desired_groups_norm:
                updates["groups"] = p["groups"]

        if not updates:
            result["changed"] = False
            result["target"] = existing
            result["msg"] = f"No changes needed for target id={existing['id']}"
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would update iSCSI target {existing['id']} with {updates}"
                )
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.target.update", existing["id"], updates)
                    result["target"] = updated
                    result["msg"] = f"Updated iSCSI target id={existing['id']}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating target {existing['id']}: {e}")
    else:
        # Create new target
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
