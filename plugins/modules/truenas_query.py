#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: truenas_query
short_description: Generic module to query TrueNAS resources
description:
  - This module allows you to call any TrueNAS middleware "query" method with optional filters and parameters.
  - For example, call C("iscsi.portal.query") with filters to find iSCSI portals matching a certain comment.
version_added: "1.0.0"
options:
  method:
    description:
      - The TrueNAS middleware query method to call, for example C("iscsi.portal.query") or C("sharing.smb.query").
    type: str
    required: true
  filters:
    description:
      - A list of query filters in TrueNAS API format. Defaults to an empty list (no filters).
      - For example: C([["comment", "=", "MyPortalComment"]]).
    type: list
    default: []
    elements: list
  params:
    description:
      - Additional parameters for the query method. Most query methods accept a second dictionary
        with various fields (e.g. C(order_by), C(limit), etc.).
      - This module merges your C(filters) into the standard `params[0]` position, and passes everything to the method.
    type: dict
    default: {}
author:
  - Your Name <you@example.com>
"""

EXAMPLES = r"""
- name: Find iSCSI portals by comment
  truenas_query:
    method: iscsi.portal.query
    filters:
      - [ "comment", "=", "MyPortalComment" ]
  register: portal_query

- name: Fail if no or multiple portals found
  fail:
    msg: "Expected exactly one portal; got {{ portal_query.json_result|length }}"
  when: portal_query.json_result|length != 1

- name: Debug the ID of the found portal
  debug:
    msg: "Portal ID = {{ portal_query.json_result[0].id }}"

- name: Query SMB shares, returning all of them
  truenas_query:
    method: sharing.smb.query
  register: smb_shares

- name: Print them
  debug:
    var: smb_shares.json_result
"""

RETURN = r"""
json_result:
  description:
    - The JSON-decoded result of the query call.
  type: list
  returned: always
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    argument_spec = dict(
        method=dict(type="str", required=True),
        filters=dict(type="list", elements="list", default=[]),
        params=dict(type="dict", default={}),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    mw = MW.client()
    method = module.params["method"]
    filters = module.params["filters"]
    params = module.params["params"]

    # For many "something.query" methods, the first argument is a list of filters,
    # and the second argument (optional) is a dictionary with additional options.
    # Example usage: mw.call("iscsi.portal.query", [filters, params])
    # We'll do something similar:
    call_args = [filters, params]

    # Example: method="iscsi.portal.query"
    # mw.call("iscsi.portal.query", [[["comment","=","value"]], {"order_by":["id"], ...}])

    try:
        if module.check_mode:
            # We do not actually call the middleware in check mode, just pretend
            module.exit_json(changed=False, json_result=[])
        result_data = mw.call(method, call_args)
    except Exception as e:
        module.fail_json(
            msg=f"Failed to call {method} with filters={filters}, params={params}: {e}"
        )

    module.exit_json(changed=False, json_result=result_data)


if __name__ == "__main__":
    main()
