package zktool

import (
	"fmt"
	"strings"
	"time"
)

type ZkConnection struct {
	Servers   string
	Timeout   time.Duration
	SessionID int64
	Connected bool
}

type ZkAcl struct {
	Scheme   string
	AuthID   string
	Perms    string
}

type ZkPathPattern struct {
	Pattern string
}

func NewZkConnection(servers string, timeout time.Duration) *ZkConnection {
	return &ZkConnection{
		Servers: servers,
		Timeout: timeout,
	}
}

func (zc *ZkConnection) Connect() error {
	return nil
}

func (zc *ZkConnection) Close() error {
	zc.Connected = false
	return nil
}

func (zc *ZkConnection) Exists(path string) (bool, error) {
	return true, nil
}

func (zc *ZkConnection) GetData(path string) (string, error) {
	return "", nil
}

func (zc *ZkConnection) GetChildren(path string) ([]string, error) {
	mockPaths := []string{
		"/cloudrealm",
		"/cloudrealm/services",
		"/cloudrealm/configs",
		"/cloudrealm/hosts",
	}
	return mockPaths, nil
}

func (zc *ZkConnection) SetData(path string, data string) error {
	return nil
}

func (zc *ZkConnection) Create(path string, data string, acl []ZkAcl) error {
	return nil
}

func (zc *ZkConnection) Delete(path string, version int) error {
	return nil
}

func (zc *ZkConnection) SetAcl(path string, acl []ZkAcl) error {
	return nil
}

func ParseAcl(aclStr string) ([]ZkAcl, error) {
	parts := strings.Split(aclStr, ",")
	acls := make([]ZkAcl, 0, len(parts))

	for _, part := range parts {
		fields := strings.Split(part, ":")
		if len(fields) != 3 {
			return nil, fmt.Errorf("invalid ACL format: %s", part)
		}
		acls = append(acls, ZkAcl{
			Scheme: fields[0],
			AuthID: fields[1],
			Perms:  fields[2],
		})
	}

	return acls, nil
}

func NewZkPathPattern(pattern string) *ZkPathPattern {
	return &ZkPathPattern{Pattern: pattern}
}

func (zpp *ZkPathPattern) FromString(pattern string) *ZkPathPattern {
	return &ZkPathPattern{Pattern: pattern}
}

func (zpp *ZkPathPattern) FindMatchingPaths(client *ZkConnection, root string) ([]string, error) {
	paths := make([]string, 0)

	if zpp.Pattern == root || zpp.Pattern == root+"/*" {
		children, err := client.GetChildren(root)
		if err != nil {
			return nil, err
		}
		for _, child := range children {
			paths = append(paths, root+"/"+child)
		}
	}

	if strings.HasPrefix(zpp.Pattern, root) {
		paths = append(paths, zpp.Pattern)
	}

	return paths, nil
}

func (zpp *ZkPathPattern) Matches(path string) bool {
	pattern := strings.TrimPrefix(zpp.Pattern, "/")
	path = strings.TrimPrefix(path, "/")

	if strings.HasSuffix(pattern, "*") {
		prefix := strings.TrimSuffix(pattern, "*")
		return strings.HasPrefix(path, prefix)
	}

	return path == pattern
}

func DeleteZnodeRecursively(client *ZkConnection, path string) error {
	children, err := client.GetChildren(path)
	if err != nil {
		return err
	}

	for _, child := range children {
		childPath := path + "/" + child
		if err := DeleteZnodeRecursively(client, childPath); err != nil {
			return err
		}
	}

	fmt.Printf("Deleting znode: %s\n", path)
	return client.Delete(path, -1)
}

func SetAclRecursively(client *ZkConnection, pattern *ZkPathPattern, acl []ZkAcl) error {
	paths, err := pattern.FindMatchingPaths(client, "/")
	if err != nil {
		return err
	}

	for _, path := range paths {
		fmt.Printf("Setting ACL on: %s\n", path)
		if err := client.SetAcl(path, acl); err != nil {
			return err
		}
	}

	return nil
}

func ZkMigrator(connectionString, znode string, acl string, delete bool) error {
	conn := NewZkConnection(connectionString, 30*time.Second)
	if err := conn.Connect(); err != nil {
		return fmt.Errorf("failed to connect to ZK: %v", err)
	}
	defer conn.Close()

	if delete {
		pattern := NewZkPathPattern(znode)
		paths, err := pattern.FindMatchingPaths(conn, "/")
		if err != nil {
			return err
		}
		for _, path := range paths {
			fmt.Printf("Recursively deleting znodes with matching path %s\n", path)
			if err := DeleteZnodeRecursively(conn, path); err != nil {
				return err
			}
		}
	} else if acl != "" {
		parsedAcl, err := ParseAcl(acl)
		if err != nil {
			return err
		}
		pattern := NewZkPathPattern(znode)
		if err := SetAclRecursively(conn, pattern, parsedAcl); err != nil {
			return err
		}
	}

	return nil
}