#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: truenas_user
short_description: Manage users on TrueNAS/FreeNAS (groups can be IDs or names), ignoring changes to specified fields on update
description:
  - Create, update, or delete a local user on TrueNAS/FreeNAS via the middleware API.
  - Primary group (C(group)) and supplemental groups (C(groups)) can be specified as integers or group names (strings).
  - If C(ignore_on_update) includes a field name, changes to that field are ignored during updates, but still applied when creating a new user.
version_added: "1.0.0"
options:
  state:
    description:
      - Whether the user should exist or not.
      - C(present) creates or updates a user,
      - C(absent) deletes it.
    type: str
    choices: [ absent, present ]
    default: present

  # Identification
  id:
    description:
      - Numeric ID of the user (for update/delete).
      - If not set, the module will look up by C(username).
    type: int
  username:
    description:
      - Username to create/update/delete.
      - If not provided but C(id) is, the module looks up by that numeric ID.
    type: str

  # Create/update fields
  uid:
    description:
      - Numeric UID (if not provided, the system auto-assigns one).
    type: int
  group:
    description:
      - Primary group, can be integer ID or string name.
      - If creating a user and C(group_create=false), this is required.
    type: raw
  group_create:
    description:
      - If true, create a new primary group with the same name as the user if none exists.
      - If false, user must specify a valid primary group in C(group).
    type: bool
  full_name:
    description:
      - Full name (GECOS) of the user.
    type: str
  home:
    description:
      - Home directory path.
    type: str
  home_mode:
    description:
      - Mode/permissions for the home directory (e.g. "0755").
    type: str
  shell:
    description:
      - Shell path (must be one of the valid shells returned by user.shell_choices).
    type: str
  email:
    description:
      - Email address for the user, or null to unset.
    type: str
  password:
    description:
      - User’s password. Required if C(password_disabled) is false.
    type: str
    no_log: true
  password_disabled:
    description:
      - If true, user cannot log in with a password.
    type: bool
  locked:
    description:
      - If true, account is locked.
    type: bool
  microsoft_account:
    description:
      - If true, treat this as a Microsoft account (affects Samba).
    type: bool
  smb:
    description:
      - If true, the user can access SMB shares (added to builtin_users group automatically).
    type: bool
  sudo:
    description:
      - If true, this user may sudo.
    type: bool
  sudo_nopasswd:
    description:
      - If true, user can sudo without providing a password.
    type: bool
  sudo_commands:
    description:
      - List of specific sudo commands allowed. If empty or not set, user can run all commands (if C(sudo) is true).
    type: list
    elements: str
  sshpubkey:
    description:
      - SSH public key, appended to the user’s authorized_keys.
    type: str
  groups:
    description:
      - List of supplemental group IDs or names (strings).
      - If a string is given, the module looks up that group by name.
      - If the name is not found, the module fails (no group creation is done here).
    type: list
    elements: raw
  attributes:
    description:
      - Arbitrary key/value pairs for user attributes.
      - e.g. {"foo": "bar"} stored under user’s general-purpose dictionary.
    type: dict

  # Delete-specific
  delete_group:
    description:
      - If true, when deleting a user, also delete their primary group if it’s not used by other users.
    type: bool
    default: false

  ignore_on_update:
    description:
      - A list of field names whose changes should be ignored on update.
      - For example, if C(["password_disabled"]) is listed, changes to password_disabled will be ignored on update
        (the old value remains), but the field is still honored on user creation.
    type: list
    elements: str
    default: []
author:
  - Your Name <you@example.com>
"""

EXAMPLES = r"""
- name: Create user 'testuser' ignoring future changes to password_disabled
  truenas_user:
    state: present
    username: testuser
    password: "abc123"
    password_disabled: false
    shell: "/usr/bin/bash"
    ignore_on_update:
      - "password_disabled"

- name: Delete user by ID
  truenas_user:
    state: absent
    id: 1010
    delete_group: true
"""

RETURN = r"""
user_id:
  description: The numeric user ID if a new user is created.
  type: int
  returned: on create
user_record:
  description:
    - Partial user record after update, or None if no update was needed.
    - (Not returned on create, since only user_id is returned.)
  type: dict
  returned: on success when state=present and existing user was updated
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    argument_spec = dict(
        state=dict(type="str", choices=["absent", "present"], default="present"),
        id=dict(type="int"),
        username=dict(type="str"),
        # Common create/update
        uid=dict(type="int"),
        group=dict(type="raw"),  # int or str
        group_create=dict(type="bool"),
        full_name=dict(type="str"),
        home=dict(type="str"),
        home_mode=dict(type="str"),
        shell=dict(type="str"),
        email=dict(type="str"),
        password=dict(type="str", no_log=True),
        password_disabled=dict(type="bool"),
        locked=dict(type="bool"),
        microsoft_account=dict(type="bool"),
        smb=dict(type="bool"),
        sudo=dict(type="bool"),
        sudo_nopasswd=dict(type="bool"),
        sudo_commands=dict(type="list", elements="str"),
        sshpubkey=dict(type="str"),
        groups=dict(type="list", elements="raw"),
        attributes=dict(type="dict"),
        # Delete-specific
        delete_group=dict(type="bool", default=False),
        # NEW: ignore_on_update
        ignore_on_update=dict(type="list", elements="str", default=[]),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    mw = MW.client()
    p = module.params
    state = p["state"]
    delete_group = p["delete_group"]
    ignored_update_fields = set(p["ignore_on_update"] or [])

    result = dict(changed=False, msg="")

    # -----------------------------------------------------------------------
    # group name -> numeric ID
    # -----------------------------------------------------------------------
    def lookup_group_id(group_val):
        """If group_val is int, return it. If str, lookup group by name. Fail if not found."""
        if isinstance(group_val, int):
            return group_val
        if not isinstance(group_val, str):
            module.fail_json(
                msg=f"Invalid group type {group_val!r}; must be int or str."
            )

        name = group_val
        try:
            gr = mw.call("group.query", [["group", "=", name]])
            if not gr:
                module.fail_json(msg=f"Group name='{name}' not found on system.")
            return gr[0]["id"]
        except Exception as e:
            module.fail_json(msg=f"Error looking up group name='{name}': {e}")

    # -----------------------------------------------------------------------
    # user lookups
    # -----------------------------------------------------------------------
    def query_user_by_id(user_id):
        try:
            users = mw.call("user.query", [["id", "=", user_id]])
            return users[0] if users else None
        except Exception as e:
            module.fail_json(msg=f"Error querying user by id={user_id}: {e}")

    def query_user_by_name(name):
        try:
            users = mw.call("user.query", [["username", "=", name]])
            return users[0] if users else None
        except Exception as e:
            module.fail_json(msg=f"Error querying user by username={name}: {e}")

    # Decide how to identify the user
    user_record = None
    if p["id"] is not None:
        user_record = query_user_by_id(p["id"])
        lookup_str = f"id={p['id']}"
    elif p["username"]:
        user_record = query_user_by_name(p["username"])
        lookup_str = f"username={p['username']}"
    else:
        lookup_str = "no id or username"

    # ------------------------------------------------
    # state=absent => delete if found
    # ------------------------------------------------
    if state == "absent":
        if not user_record:
            result["changed"] = False
            result["msg"] = f"No user found with {lookup_str}, nothing to delete."
            module.exit_json(**result)
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would delete user {user_record['username']} (id={user_record['id']})"
                )
                result["changed"] = True
                module.exit_json(**result)
            try:
                mw.call(
                    "user.delete", user_record["id"], {"delete_group": delete_group}
                )
                result["changed"] = True
                result["msg"] = (
                    f"Deleted user id={user_record['id']} username={user_record['username']}"
                )
                module.exit_json(**result)
            except Exception as e:
                module.fail_json(msg=f"Error deleting user id={user_record['id']}: {e}")

    # ------------------------------------------------
    # state=present => create or update
    # ------------------------------------------------
    is_new = user_record is None

    # Basic validations
    if p["password_disabled"] is False and not p["password"]:
        module.fail_json(msg="password is required if password_disabled=false.")
    if is_new and not p["username"]:
        module.fail_json(
            msg="username is required to create a new user (if no id is specified)."
        )
    if is_new and p["group_create"] is False and (p["group"] is None):
        module.fail_json(
            msg="group is required if group_create=false when creating a new user."
        )

    # --- CREATE ---
    if is_new:
        payload = {"username": p["username"]}
        if p["uid"] is not None:
            payload["uid"] = p["uid"]
        if p["group_create"] is False and p["group"] is not None:
            payload["group"] = lookup_group_id(p["group"])
        if p["group_create"] is not None:
            payload["group_create"] = p["group_create"]

        if p["password"] is not None:
            payload["password"] = p["password"]
        if p["password_disabled"] is not None:
            payload["password_disabled"] = p["password_disabled"]

        # Additional fields
        for field in [
            "full_name",
            "home",
            "home_mode",
            "shell",
            "email",
            "locked",
            "microsoft_account",
            "smb",
            "sudo",
            "sudo_nopasswd",
            "sshpubkey",
            "attributes",
        ]:
            val = p[field]
            if val is not None:
                payload[field] = val

        if p["sudo_commands"] is not None:
            payload["sudo_commands"] = p["sudo_commands"]

        # For supplemental groups
        if p["groups"] is not None:
            resolved_sup_grps = []
            for g in p["groups"]:
                resolved_sup_grps.append(lookup_group_id(g))
            payload["groups"] = resolved_sup_grps

        if module.check_mode:
            result["changed"] = True
            result["msg"] = f"Would create new user: {payload}"
            module.exit_json(**result)

        # Actually create
        try:
            new_id = mw.call("user.create", payload)
            # user.create returns the new user ID (integer).
            result["changed"] = True
            result["msg"] = f"Created new user with id={new_id}"
            result["user_id"] = new_id
            module.exit_json(**result)
        except Exception as e:
            module.fail_json(msg=f"Error creating user {p['username']}: {e}")

    # --- UPDATE ---
    else:
        # We have an existing user => user.update
        user_id = user_record["id"]
        updates = {}

        # Helper for fields
        def maybe_set(field):
            """
            If we have a new value, and it differs from existing,
            we set it in updates. But if field is in ignored_update_fields, skip it.
            """
            if field in ignored_update_fields:
                return  # skip applying changes for this field
            val = p[field]
            if val is not None and val != user_record.get(field):
                updates[field] = val

        maybe_set("uid")
        maybe_set("username")
        maybe_set("home")
        maybe_set("home_mode")
        maybe_set("shell")
        maybe_set("full_name")
        maybe_set("email")
        maybe_set("password")
        maybe_set("password_disabled")
        maybe_set("locked")
        maybe_set("microsoft_account")
        maybe_set("smb")
        maybe_set("sudo")
        maybe_set("sudo_nopasswd")
        maybe_set("sshpubkey")

        # If user provided a group, we must resolve it to numeric (unless ignored)
        if "group" not in ignored_update_fields and p["group"] is not None:
            desired_gid = lookup_group_id(p["group"])
            if desired_gid != user_record.get("group"):
                updates["group"] = desired_gid

        # Compare sudo_commands
        if (
            "sudo_commands" not in ignored_update_fields
            and p["sudo_commands"] is not None
        ):
            ex_cmds = user_record.get("sudo_commands") or []
            desired_cmds = p["sudo_commands"]
            if sorted(ex_cmds) != sorted(desired_cmds):
                updates["sudo_commands"] = desired_cmds

        # Compare supplemental groups
        if "groups" not in ignored_update_fields and p["groups"] is not None:
            ex_grps = user_record.get("groups") or []
            resolved = [lookup_group_id(g) for g in p["groups"]]
            if set(ex_grps) != set(resolved):
                updates["groups"] = resolved

        # Compare attributes
        if "attributes" not in ignored_update_fields and p["attributes"] is not None:
            ex_attr = user_record.get("attributes") or {}
            if ex_attr != p["attributes"]:
                updates["attributes"] = p["attributes"]

        if not updates:
            result["changed"] = False
            result["msg"] = (
                f"No changes needed for user id={user_id} (username={user_record['username']})"
            )
            module.exit_json(**result)

        if module.check_mode:
            result["changed"] = True
            result["msg"] = f"Would update user id={user_id} with {updates}"
            module.exit_json(**result)

        try:
            updated_record = mw.call("user.update", user_id, updates)
            # Typically returns the updated user dictionary
            result["changed"] = True
            result["msg"] = f"Updated user id={user_id}"
            result["user_record"] = updated_record
            module.exit_json(**result)
        except Exception as e:
            module.fail_json(msg=f"Error updating user id={user_id}: {e}")


if __name__ == "__main__":
    main()
