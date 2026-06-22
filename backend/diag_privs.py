import psycopg2

HOST='177.85.99.66'
DB='medsoft_medmigra'
USER='medsoft_migra'
PASS='Alemanha2025@'
PORT=5432

def main():
    conn = psycopg2.connect(host=HOST, database=DB, user=USER, password=PASS, port=PORT)
    cur = conn.cursor()
    print('Checking role memberships for medsoft_master:')
    cur.execute("SELECT rolname FROM pg_roles WHERE oid IN (SELECT roleid FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname=%s))", (USER,))
    rows = cur.fetchall()
    print('Member of roles:', [r[0] for r in rows])

    print('\nChecking table ACLs containing medsoft_master:')
    cur.execute("""
        SELECT n.nspname, c.relname, c.relacl
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' -- regular tables
          AND n.nspname NOT IN ('pg_catalog','information_schema')
        ORDER BY n.nspname, c.relname
    """)
    found = False
    for nsp, rel, acl in cur.fetchall():
        if acl:
            # acl is like {"user=arwdDxt/user","..."}
            acl_str = str(acl)
            if USER in acl_str:
                print(f'  {nsp}.{rel}: {acl}')
                found = True
    if not found:
        print('  No explicit table ACL entries found for', USER)

    print('\nChecking information_schema.table_privileges for medsoft_master:')
    cur.execute("SELECT grantee, table_schema, table_name, privilege_type FROM information_schema.table_privileges WHERE grantee=%s ORDER BY table_schema, table_name", (USER,))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(' ', r)
    else:
        print('  (no rows)')

    conn.close()

if __name__ == '__main__':
    main()
