#!/usr/bin/env python3
from impacket.smbconnection import SMBConnection, SessionError
from impacket.smb3structs import FILE_READ_DATA, FILE_WRITE_DATA
from impacket.dcerpc.v5 import samr, epm, transport, rpcrt, rprn
from impacket.dcerpc.v5.rpcrt import DCERPCException, RPC_C_AUTHN_WINNT, RPC_C_AUTHN_LEVEL_PKT_PRIVACY

from powerview.utils.helpers import get_machine_name, ldap3_kerberos_login

import ssl
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
        self.use_gc = args.use_gc
        self.use_gc_ldaps = args.use_gc_ldaps
        self.hashes = args.hashes
        self.auth_aes_key = args.auth_aes_key
        self.no_pass = args.no_pass
        self.args = args
        self.targetIp = args.dc_ip
        self.kdcHost = args.dc_ip

        self.samr = None
        self.TGT = None
        self.TGS = None

    def init_ldap_session(self):
        if self.use_kerberos:
            target = get_machine_name(self.args, self.domain)
            self.kdcHost = target
            #target = get_machine_name(self.args, self.domain)
        else:
            if self.dc_ip is not None:
                target = self.dc_ip
            else:
                target = self.domain

        if self.use_ldaps is True or self.use_gc_ldaps is True:
            try:
                return self.init_ldap_connection(target, ssl.PROTOCOL_TLSv1_2, self.domain, self.username, self.password, self.lmhash, self.nthash)
            except ldap3.core.exceptions.LDAPSocketOpenError:
                try:
                    return self.init_ldap_connection(target, ssl.PROTOCOL_TLSv1, self.domain, self.username, self.password, self.lmhash, self.nthash)
                except:
                    if self.use_ldaps:
                        logging.error('Error bind to LDAPS, falling back to LDAP')
                        self.use_ldaps = False
                    elif self.use_gc_ldaps:
                        logging.error('Error bind to LDAPS, falling back to GC ssl')
                        self.use_gc = True
                        self.use_gc_ldaps = False
                    return self.init_ldap_connection(target, None, self.domain, self.username, self.password, self.lmhash, self.nthash)
        else:
            return self.init_ldap_connection(target, None, self.domain, self.username, self.password, self.lmhash, self.nthash)

    def init_ldap_connection(self, target, tls, domain, username, password, lmhash, nthash):
        user = '%s\\%s' % (domain, username)

        if tls:
            if self.use_ldaps:
                use_ssl = True
                port = 636
            elif self.use_gc_ldaps:
                use_ssl = True
                port = 3269
        else:
            if self.use_gc:
                use_ssl = False
                port = 3268
            else:
                use_ssl = False
                port = 389

        # TODO: fix target when using kerberos
        logging.debug(f"Connecting to {target} Port: {port}, SSL: {use_ssl}")
        ldap_server = ldap3.Server(target, get_info=ldap3.ALL, port=port, use_ssl=use_ssl)
        if self.use_kerberos:
            ldap_session = ldap3.Connection(ldap_server, auto_referrals=False)
            ldap_session.bind()
            ldap3_kerberos_login(ldap_session, target, username, password, domain, lmhash, nthash, self.auth_aes_key, kdcHost=self.kdcHost,useCache=self.no_pass)
        elif self.hashes is not None:
            ldap_session = ldap3.Connection(ldap_server, user=user, password=lmhash + ":" + nthash, authentication=ldap3.NTLM, auto_bind=True)
        else:
            ldap_session = ldap3.Connection(ldap_server, user=user, password=password, authentication=ldap3.NTLM, auto_bind=True)

        return ldap_server, ldap_session

    def init_smb_session(self, host, timeout=10):
        try:
            logging.debug("Default timeout is set to 15. Expect a delay")
            conn = SMBConnection(host, host, sess_port=445, timeout=timeout)
            if self.use_kerberos:
                # only import if used
                import os
                from impacket.krb5.ccache import CCache
                from impacket.krb5.kerberosv5 import KerberosError
                from impacket.krb5 import constants

                try:
                    ccache = CCache.loadFile(os.getenv('KRB5CCNAME'))
                except Exception as e:
                   # No cache present
                    logging.error(str(e))
                    pass
                else:
                    # retrieve domain information from CCache file if needed
                    if self.domain == '':
                        self.domain = ccache.principal.realm['data'].decode('utf-8')
                        logging.debug('Domain retrieved from CCache: %s' % domain)

                    logging.debug('Using Kerberos Cache: %s' % os.getenv('KRB5CCNAME'))
                    principal = 'cifs/%s@%s' % (self.targetIp.upper(), self.domain.upper())

                    creds = ccache.getCredential(principal)
                    if creds is None:
                        # Let's try for the TGT and go from there
                        principal = 'krbtgt/%s@%s' % (self.domain.upper(), self.domain.upper())
                        creds = ccache.getCredential(principal)
                        if creds is not None:
                            self.TGT = creds.toTGT()
                            logging.debug('Using TGT from cache')
                        else:
                            logging.debug('No valid credentials found in cache')
                    else:
                        self.TGS = creds.toTGS(principal)
                        logging.debug('Using TGS from cache')

                    # retrieve user information from CCache file if needed
                    if self.username == '' and creds is not None:
                        self.username = creds['client'].prettyPrint().split(b'@')[0].decode('utf-8')
                        logging.debug('Username retrieved from CCache: %s' % self.username)
                    elif self.username == '' and len(ccache.principal.components) > 0:
                        self.user = ccache.principal.components[0]['data'].decode('utf-8')
                        logging.debug('Username retrieved from CCache: %s' % self.username)

                    conn.kerberosLogin(self.username,self.password,self.domain, self.lmhash, self.nthash, self.auth_aes_key, self.dc_ip, self.TGT, self.TGS)
                    #conn.kerberosLogin(self.username,self.password,self.domain, self.lmhash, self.nthash, self.auth_aes_key, self.dc_ip, self.TGT, self.TGS)
                    # havent support kerberos authentication yet
            else:
                conn.login(self.username,self.password,self.domain, self.lmhash, self.nthash)
            return conn
        except OSError as e:
            logging.debug(str(e))
            return None
        except SessionError as e:
            logging.debug(str(e))
            return None
        except AssertionError as e:
            logging.debug(str(e))
            return None

    def init_samr_session(self):
        if not self.samr:
            self.samr = self.connectSamr()
        return self.samr

    # TODO: FIX kerberos auth
    def connectSamr(self):
        rpctransport = transport.SMBTransport(self.dc_ip, filename=r'\samr')

        #if self.nthash:
        if hasattr(rpctransport, 'set_credentials'):
            rpctransport.set_credentials(self.username, self.password, self.domain, lmhash=self.lmhash, nthash=self.nthash, aesKey=self.auth_aes_key)
        #else:
        #    rpctransport.set_credentials(self.username, self.password, self.domain)

        rpctransport.set_kerberos(self.use_kerberos, kdcHost=self.kdcHost)

        try:
            dce = rpctransport.get_dce_rpc()
            dce.set_auth_level(rpcrt.RPC_C_AUTHN_LEVEL_PKT_PRIVACY)
            dce.connect()
            dce.bind(samr.MSRPC_UUID_SAMR)
            return dce
        except:
            return None

    # stole from PetitPotam.py
    # TODO: FIX kerberos auth
    def connectRPCTransport(self, host=None, stringBindings=None, auth=True):
        if not stringBindings:
            stringBindings = epm.hept_map(host, samr.MSRPC_UUID_SAMR, protocol = 'ncacn_ip_tcp')
        if not host:
            host = self.dc_ip

        rpctransport = transport.DCERPCTransportFactory(stringBindings)
        #rpctransport.set_dport(445)

        if hasattr(rpctransport, 'set_credentials') and auth:
            rpctransport.set_credentials(self.username, self.password, self.domain, self.lmhash, self.nthash)

        rpctransport.set_kerberos(self.use_kerberos, kdcHost=self.kdcHost)

        if host:
            rpctransport.setRemoteHost(host)

        dce = rpctransport.get_dce_rpc()
        dce.set_auth_type(RPC_C_AUTHN_WINNT)
        dce.set_auth_level(RPC_C_AUTHN_LEVEL_PKT_PRIVACY)

        logging.debug("Connecting to %s" % stringBindings)

        try:
            dce.connect()
            return dce
        except Exception as e:
            return None
