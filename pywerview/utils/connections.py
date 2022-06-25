#!/usr/bin/env python3
from impacket.smbconnection import SMBConnection, SessionError

import ldap3
import logging

class CONNECTION:
    def __init__(self, args):
        self.username = args.username
        self.password = args.password
        self.domain = args.domain
        self.lmhash = args.lmhash
        self.nthash = args.nthash
        self.use_kerberos = args.use_kerberos
        self.dc_ip = args.dc_ip
        self.use_ldaps = args.use_ldaps
        self.hashes = args.hashes
        self.no_pass = args.no_pass
        self.args = args

    def init_ldap_session(self):
        if self.use_kerberos:
            target = get_machine_name(self.args, self.domain)
        else:
            if self.dc_ip is not None:
                target = self.dc_ip
            else:
                target = domain

        if self.use_ldaps is True:
            try:
                return self.init_ldap_connection(target, ssl.PROTOCOL_TLSv1_2, self.args, self.domain, self.username, self.password, self.lmhash, self.nthash)
            except ldap3.core.exceptions.LDAPSocketOpenError:
                return self.init_ldap_connection(target, ssl.PROTOCOL_TLSv1, self.args, self.domain, self.username, self.password, self.lmhash, self.nthash)
        else:
            return self.init_ldap_connection(target, None, self.domain, self.username, self.password, self.lmhash, self.nthash)

    def init_ldap_connection(self, target, no_tls, domain, username, password, lmhash, nthash): 
        user = '%s\\%s' % (domain, username)
        if not no_tls:
            use_ssl = False
            port = 389
        else:
            use_ssl = True
            port = 636
        ldap_server = ldap3.Server(target, get_info=ldap3.ALL, port=port, use_ssl=use_ssl)
        if self.use_kerberos:
            ldap_session = ldap3.Connection(ldap_server)
            ldap_session.bind()
            ldap3_kerberos_login(ldap_session, target, username, password, domain, lmhash, nthash, self.auth_aes_key, kdcHost=self.dc_ip,useCache=self.no_pass)
        elif self.hashes is not None:
            ldap_session = ldap3.Connection(ldap_server, user=user, password=lmhash + ":" + nthash, authentication=ldap3.NTLM, auto_bind=True)
        else:
            ldap_session = ldap3.Connection(ldap_server, user=user, password=password, authentication=ldap3.NTLM, auto_bind=True)

        return ldap_server, ldap_session

    def init_smb_session(self, host):
        try:
            conn = SMBConnection(host, host, sess_port=445, timeout=15)
            conn.login(self.username,self.password,self.domain, self.lmhash, self.nthash)
            return conn
        except OSError as e:
            logging.error(e)
            return None