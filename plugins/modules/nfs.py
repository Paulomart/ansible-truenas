#!/usr/bin/python
__metaclass__ = type

# XXX - Options
# x servers(int, 1-256): number of nfsd servers
# x udp (bool)
# x allow_nonroot (bool)
# x v4 (bool)
# x v4_v3owner (bool)
# x v4_krb (bool)
# x v4_domain (str)
# x bindip (list of ip addrs)
# x mountd_port (int)
# x rpcstatd_port (int)
# x rpclockd_port (int)
# - mountd_log (bool)
# x userd_manage_gids (bool)
# - statd_lockd_log (bool)

DOCUMENTATION = '''
---
module: nfs
short_description: Configure NFS service
description:
  - Configure the NFS service.
  - For individual NFS exports, see C(sharing_nfs)
options:
  udp:
    description:
      - If true, serve UDP clients. Use this if you have NFS clients
        that have to use UDP.
      - This sets the C(-u) option to C(nfsd).
    type: bool
  allow_nonroot:
    description:
      - When true, allow non-root requests to be served.
      - Sets the C(-n) option to C(mountd).
    type: bool
  nfsv4:
    description:
      - If true, enable NFSv4. Otherwise, use NFSv3.
    type: bool
  servers:
    description:
      - The number of NFS servers to create. This value is passed
        to the C(-n) parameter of C(nfsd).
    type: int
  v3owner:
    description:
      - Enable the NFSv3 ownership model for NFSv4.
      - Ignored unless C(nfsv4) is true.
  krb:
    description:
      - Turn on Kerberos for NFSv4. Forces shares to fail without a
        Kerberos ticket.
      - This enables the C(gssd) daemon.
      - Ignored unless C(nfsv4) is true.
  domain:
    description:
      - Overrides the default DNS domain name for NFSv4.
      - Passes the C(-domain) option to C(nfsuserd).
      - Ignored unless C(nfsv4) is true.
    type: str
  bindip:
    description:
      - List of IP addresses on which to listen for NFS requests.
        When this is the empty list, listen on all available addresses.
    type: list
    elements: str
  mountd_port:
    description:
      - Specifies the port that C(mountd) should bind to.
      - This passes the C(-p) option to C(mountd).
    type: int
  rpcstatd_port:
    description:
      - Specifies the port that C(rpc.statd) binds to.
      - This passes the C(-p) option to C(rpc.statd).
    type: int
  rpclockd_port:
    description:
      - Specifies the port that C(rpc.lockd) binds to.
      - This passes the C(-p) option to C(rpc.lockd).
    type: int
  userd_manage_gids:
    description:
      - Use this when a user is a member of more than 16 groups.
      - Passes the C(-manage-gids) option to C(nfsuserd).
    type: bool
version_added: 0.4.0
'''

# XXX
EXAMPLES = '''
- name: Enable NFSv4
  hosts: nfs_server
  become: yes
  tasks:
    - arensb.truenas.nfs:
        nfsv4: yes
'''

# XXX
RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware \
    import MiddleWare as MW


def main():
    module = AnsibleModule(
        argument_spec=dict(
            servers=dict(type='int'),
            udp=dict(type='bool'),
            allow_nonroot=dict(type='bool'),
            nfsv4=dict(type='bool'),
            v3owner=dict(type='bool'),
            krb=dict(type='bool'),
            domain=dict(type='str'),
            bindip=dict(type='list', elements='str'),
            mountd_port=dict(type='int'),
            rpcstatd_port=dict(type='int'),
            rpclockd_port=dict(type='int'),
            userd_manage_gids=dict(type='bool'),
            ),
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        msg=''
    )

    mw = MW.client()

    # Assign variables from properties, for convenience
    servers = module.params['servers']
    udp = module.params['udp']
    allow_nonroot = module.params['allow_nonroot']
    nfsv4 = module.params['nfsv4']
    v3owner = module.params['v3owner']
    krb = module.params['krb']
    domain = module.params['domain']
    bindip = module.params['bindip']
    mountd_port = module.params['mountd_port']
    rpcstatd_port = module.params['rpcstatd_port']
    rpclockd_port = module.params['rpclockd_port']
    userd_manage_gids = module.params['userd_manage_gids']

    # Look up the resource
    try:
        nfs_info = mw.call("nfs.config")
    except Exception as e:
        module.fail_json(msg=f"Error looking up nfs configuration: {e}")

    # Make list of differences between what is and what should
    # be.
    arg = {}

    if servers is not None and nfs_info['servers'] != servers:
        arg['servers'] = servers

    if udp is not None and nfs_info['udp'] is not udp:
        arg['udp'] = udp

    if allow_nonroot is not None and nfs_info['allow_nonroot'] \
       is not allow_nonroot:
        arg['allow_nonroot'] = allow_nonroot

    if nfsv4 is not None and nfs_info['v4'] != nfsv4:
        arg['v4'] = nfsv4

    if v3owner is not None and nfs_info['v4_v3owner'] is not v3owner:
        arg['v4_v3owner'] = v3owner

    if krb is not None and nfs_info['v4_krb'] is not krb:
        arg['v4_krb'] = krb

    if domain is not None and nfs_info['v4_domain'] != domain:
        arg['v4_domain'] = domain

    if bindip is not None and \
       set(bindip) != set(nfs_info['bindip']):
        arg['bindip'] = bindip

    if mountd_port is not None and nfs_info['mountd_port'] != mountd_port:
        arg['mountd_port'] = mountd_port

    if rpcstatd_port is not None and \
       nfs_info['rpcstatd_port'] != rpcstatd_port:
        arg['rpcstatd_port'] = rpcstatd_port

    if rpclockd_port is not None and \
       nfs_info['rpclockd_port'] != rpclockd_port:
        arg['rpclockd_port'] = rpclockd_port

    if userd_manage_gids is not None and \
       nfs_info['userd_manage_gids'] is not userd_manage_gids:
        arg['userd_manage_gids'] = userd_manage_gids

    # If there are any changes, nfs.update()
    if len(arg) == 0:
        # No changes
        result['changed'] = False
    else:
        #
        # Update nfs.
        #
        if module.check_mode:
            result['msg'] = f"Would have updated nfs: {arg}"
        else:
            try:
                err = mw.call("nfs.update",
                              arg)
            except Exception as e:
                module.fail_json(msg=f"Error updating nfs with {arg}: {e}")
                # Return any interesting bits from err
                result['status'] = err['status']
        result['changed'] = True

    module.exit_json(**result)


# Main
if __name__ == "__main__":
    main()
