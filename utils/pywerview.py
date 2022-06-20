#!/usr/bin/env python3

class PywerView:
    
    def __init__(self,ldap_session,root_dn):
        self.ldap_session = ldap_session
        self.root_dn = root_dn

    def get_domainuser(self, args, properties='*'):
        if args.preauthnotrequired:
            ldap_filter = f'(&(samAccountType=805306368)(userAccountControl:1.2.840.113556.1.4.803:=4194304)(sAMAccountName={args.identity}))'
        elif args.admincount:
            ldap_filter = f'(&(samAccountType=805396368)(adminCount=1)(sAMAccountName={args.identity}))'
        elif args.allowdelegation:
            ldap_filter = f'(&(samAccountType=805306368)!(userAccountControl:1.2.840.113556.1.4.803:=1048574)(sAMAccountName={args.identity}))'
        elif args.trustedtoauth:
            ldap_filter = f'(&(samAccountType=805306368)(msds-allowedtodelegateto=*)(sAMAccountName={args.identity}))'
        elif args.spn:
            ldap_filter = f'(&(samAccountType=805306368)(servicePrincipalName=*)(sAMAccountName={args.identity}))'
        else:
            ldap_filter = f'(&(samAccountType=805306368)(sAMAccountName={args.identity}))'

        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries

    def get_domaincontroller(self, args, properties='*'):
        ldap_filter = f'(userAccountControl:1.2.840.113556.1.4.803:=8192)'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries

    def get_domaincomputer(self, args, properties='*'):
        if args.unconstrained:
            ldap_filter = f'(&(samAccountType=805306369)(userAccountControl:1.2.840.113556.1.4.803:=524288)(sAMAccountName={args.identity}))'
        elif args.trustedtoauth:
            ldap_filter = f'(&(samAccountType=805306369)(msds-allowedtodelegateto=*)(sAMAccountName={args.identity}))'
        else:
            ldap_filter = f'(&(samAccountType=805306369)(sAMAccountName={args.identity}))'
        
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries
        #for entry in self.ldap_session.entries:
        #    print(entry.entry_to_ldif())
    
    def get_domaingroup(self, args, properties='*'):
        ldap_filter = f'(&(objectCategory=group)(name={args.identity}))'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries
    
    def get_domaingpo(self, args, properties='*'):
        ldap_filter = f'(&(objectCategory=groupPolicyContainer)(cn={args.identity}))'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries
    
    def get_domaintrust(self, args, properties='*'):
        ldap_filter = f'(objectClass=trustedDomain)'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries
    
    def get_domain(self, args, properties='*'):
        ldap_filter = f'(objectClass=domain)'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=properties)
        return self.ldap_session.entries
    
    def add_domaingroupmember(self, args):
        ldap_filter = f'(&(objectCategory=group)(name={args.identity}))'
        self.ldap_session.search(self.root_dn,ldap_filter,attributes=['distinguishedname'])
        identity_dn = self.ldap_session.entries[0].entry_dn

        self.ldap_session.modify(identity_dn, {'member':[ldap3.MODIFY, [args.members]]})
