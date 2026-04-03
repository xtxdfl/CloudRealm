-- Add missing columns to hosts table
ALTER TABLE hosts ADD COLUMN available_mem bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN available_disk bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN storage_size bigint(20) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN memory_usage decimal(38,2) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN disk_usage decimal(38,2) DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN ssh_private_key TEXT DEFAULT NULL;
ALTER TABLE hosts ADD COLUMN ssh_public_key TEXT DEFAULT NULL;