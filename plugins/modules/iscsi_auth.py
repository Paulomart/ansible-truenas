#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_auth
short_description: Manage iSCSI Authorized Access
description:
  - Create, update, and delete iSCSI Authorized Access records.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the auth record should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - ID of an existing iSCSI Auth record (for update or delete).
    type: int
  tag:
    description:
      - CHAP tag (must be unique among iSCSI auth records).
    type: int
  user:
    description:
      - CHAP username.
    type: str
  secret:
    description:
      - CHAP secret (12-16 characters).
    type: str
    no_log: true
  peeruser:
    description:
      - Username for mutual CHAP.
    type: str
  peersecret:
    description:
      - CHAP secret for mutual CHAP (12-16 characters, cannot be the same as secret).
    type: str
    no_log: true
"""

EXAMPLES = r"""
- name: Create an iSCSI auth record
  iscsi_auth:
    state: present
    tag: 1
    user: "chap_user"
    secret: "myChapSecret1"
    peeruser: "peer_chap_user"
    peersecret: "myPeerSecret2"

- name: Update an iSCSI auth record
  iscsi_auth:
    state: present
    id: 3
    user: "new_chap_user"
    secret: "newChapSecret!"

- name: Delete an iSCSI auth record
  iscsi_auth:
    state: absent
    id: 4
"""

RETURN = r"""
auth_record:
  description:
    - A data structure describing the created or updated iSCSI Authorized Access.
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
            tag=dict(type="int"),
            user=dict(type="str"),
            secret=dict(type="str", no_log=True),
            peeruser=dict(type="str"),
            peersecret=dict(type="str", no_log=True),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]
    record_id = params["id"]

    # Helper: find existing record by ID
    def find_auth_by_id(auth_id):
        try:
            recs = mw.call("iscsi.auth.query", [["id", "=", auth_id]])
            return recs[0] if recs else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI auth (id={auth_id}): {e}")

    existing = None
    if record_id is not None:
        existing = find_auth_by_id(record_id)

    # --------------------------------------------------------
    # state=absent
    # --------------------------------------------------------
    if state == "absent":
        if not record_id:
            module.fail_json(msg="id is required to delete iSCSI auth.")
        if existing is None:
            # Already does not exist
            result["changed"] = False
            result["msg"] = "Auth record does not exist."
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted auth record {record_id}"
            else:
                try:
                    mw.call("iscsi.auth.delete", record_id)
                except Exception as e:
                    module.fail_json(msg=f"Error deleting auth record {record_id}: {e}")
                result["msg"] = f"Deleted auth record {record_id}"
            result["changed"] = True
        module.exit_json(**result)

    # --------------------------------------------------------
    # state=present (create or update)
    # --------------------------------------------------------
    # Validate secrets if provided
    if params["secret"] and not (12 <= len(params["secret"]) <= 16):
        module.fail_json(msg="secret must be 12-16 characters.")
    if params["peersecret"]:
        if not (12 <= len(params["peersecret"]) <= 16):
            module.fail_json(msg="peersecret must be 12-16 characters.")
        if params["secret"] and params["peersecret"] == params["secret"]:
            module.fail_json(msg="peersecret must not match secret.")

    if existing:
        # Update
        to_update = {}
        if params["tag"] is not None and existing.get("tag") != params["tag"]:
            to_update["tag"] = params["tag"]
        if params["user"] is not None and existing.get("user") != params["user"]:
            to_update["user"] = params["user"]
        if params["secret"] is not None and existing.get("secret") != params["secret"]:
            to_update["secret"] = params["secret"]
        if (
            params["peeruser"] is not None
            and existing.get("peeruser") != params["peeruser"]
        ):
            to_update["peeruser"] = params["peeruser"]
        if (
            params["peersecret"] is not None
            and existing.get("peersecret") != params["peersecret"]
        ):
            to_update["peersecret"] = params["peersecret"]

        if not to_update:
            result["changed"] = False
            result["auth_record"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would have updated auth id={record_id} with {to_update}"
                )
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.auth.update", record_id, to_update)
                    result["msg"] = f"Updated auth record {record_id}"
                    result["auth_record"] = updated
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating auth record {record_id}: {e}")
    else:
        # Create
        if (
            (params["tag"] is None)
            or (params["user"] is None)
            or (params["secret"] is None)
        ):
            module.fail_json(
                msg="tag, user, and secret are required to create a new iSCSI auth record."
            )

        payload = dict(
            tag=params["tag"],
            user=params["user"],
            secret=params["secret"],
        )
        if params["peeruser"] is not None:
            payload["peeruser"] = params["peeruser"]
        if params["peersecret"] is not None:
            payload["peersecret"] = params["peersecret"]

        if module.check_mode:
            result["msg"] = f"Would have created new auth record: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.auth.create", payload)
                result["msg"] = f"Created new auth record"
                result["auth_record"] = created
                result["changed"] = True
            except Exception as e:
                module.fail_json(msg=f"Error creating new auth record: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
