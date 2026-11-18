-- 20260731_users_password_hash.sql
--
-- Security finding 4 (CRITICAL): login compared the submitted password with
-- literals in services/api/server.js ("Factory@123", "my", "hwg"). Credentials
-- now live in users.password_hash and the API verifies them with a constant-time
-- scrypt comparison.
--
-- Hash format:  scrypt$N$r$p$<base64 salt>$<base64 derived key>
-- KDF params :  N=16384, r=8, p=1, keyLen=64, 16-byte random salt
-- Verification: services/api/server.js -> verifyPasswordHash()
--
-- Existing accounts are backfilled with a hash of their current password so
-- nobody is locked out; MENG_YING/HWG keep their historical passwords.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_updated_at timestamp with time zone;

COMMENT ON COLUMN users.password_hash IS
  'scrypt$N$r$p$<salt>$<hash> password verifier; NULL denies login (see services/api/server.js verifyPasswordHash)';
COMMENT ON COLUMN users.password_updated_at IS
  'When password_hash was last set; rotate here, never in application source';

UPDATE users
SET password_hash = CASE username
      WHEN 'MENG_YING' THEN 'scrypt$16384$8$1$sMAjzKf4cPybduLHyZydvg==$GrK6UXr3RzZt36GxkYTJg/1A4waQDZAg4jNtWNN36PgLjc1TbNpLvlHUjwTHxWr9/tbAUZ40bC0zDB2538nmuA=='
      WHEN 'HWG' THEN 'scrypt$16384$8$1$qQJmeYy3aNE5I6smeHw0bw==$03LWjBwfZ6juacuRnMX1DJOC7mSALzZ155S55elDpNHY1m9COuVx/ur6ocasG21fv4usemGpfWw0U0ZqhH+geg=='
      ELSE 'scrypt$16384$8$1$6rc6zOUXsz/RrYeiLWhdKw==$4v0oj9sP6kBMWiuc+SEjaUfrUzgeWKYRi62xq162zl/+jVN1LWP7Sau6hWkTUbpquACWA263Mxvy3pILcgMXMQ=='
    END,
    password_updated_at = now()
WHERE password_hash IS NULL;

-- Every account in this database carries the hash of the password it used
-- before this migration, i.e. Factory@123 for all non-special accounts.
DO $$
DECLARE
  missing integer;
BEGIN
  SELECT count(*) INTO missing FROM users WHERE password_hash IS NULL;
  IF missing > 0 THEN
    RAISE EXCEPTION 'users.password_hash bootstrap incomplete: % account(s) have no verifier', missing;
  END IF;
END
$$;
