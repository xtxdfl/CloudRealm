package utils

import (
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func FileMD5(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	hash := md5.Sum(data)
	return hex.EncodeToString(hash[:]), nil
}

func FileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func FileSize(path string) (int64, error) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, err
	}
	return info.Size(), nil
}

func FileModifiedTime(path string) (time.Time, error) {
	info, err := os.Stat(path)
	if err != nil {
		return time.Time{}, err
	}
	return info.ModTime(), nil
}

func EnsureDir(path string) error {
	return os.MkdirAll(path, 0755)
}

func GetAbsolutePath(path string) (string, error) {
	if filepath.IsAbs(path) {
		return path, nil
	}
	return filepath.Abs(path)
}

func CopyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0644)
}

func ReadFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func WriteFile(path, content string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0644)
}

func StringToFile(path, content string) error {
	return WriteFile(path, content)
}

func FileToString(path string) (string, error) {
	return ReadFile(path)
}

func JoinPath(parts ...string) string {
	return filepath.Join(parts...)
}

func GetFileName(path string) string {
	return filepath.Base(path)
}

func GetFileExt(path string) string {
	return filepath.Ext(path)
}

func GetDirName(path string) string {
	return filepath.Dir(path)
}

func StringsJoin(sep string, parts ...string) string {
	return strings.Join(parts, sep)
}

func StringsSplit(s, sep string) []string {
	return strings.Split(s, sep)
}

func StringsTrim(s string) string {
	return strings.TrimSpace(s)
}

func StringsContains(s, substr string) bool {
	return strings.Contains(s, substr)
}

func StringsHasPrefix(s, prefix string) bool {
	return strings.HasPrefix(s, prefix)
}

func StringsHasSuffix(s, suffix string) bool {
	return strings.HasSuffix(s, suffix)
}

func StringsReplace(s, old, new string) string {
	return strings.ReplaceAll(s, old, new)
}

func ToLower(s string) string {
	return strings.ToLower(s)
}

func ToUpper(s string) string {
	return strings.ToUpper(s)
}

func FormatBytes(size int64) string {
	const unit = 1024
	if size < unit {
		return fmt.Sprintf("%d B", size)
	}
	div, exp := int64(unit), 0
	for n := size / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.2f %cB", float64(size)/float64(div), "KMGTPE"[exp])
}

func FormatDuration(d time.Duration) string {
	if d < time.Second {
		return fmt.Sprintf("%dms", d.Milliseconds())
	}
	if d < time.Minute {
		return fmt.Sprintf("%.1fs", d.Seconds())
	}
	if d < time.Hour {
		return fmt.Sprintf("%.1fm", d.Minutes())
	}
	return fmt.Sprintf("%.1fh", d.Hours())
}

func ParseBool(s string) bool {
	s = strings.ToLower(strings.TrimSpace(s))
	return s == "true" || s == "1" || s == "yes" || s == "on"
}

func DefaultString(s, defaultValue string) string {
	if s == "" {
		return defaultValue
	}
	return s
}

func DefaultIfEmpty(s, defaultValue string) string {
	if strings.TrimSpace(s) == "" {
		return defaultValue
	}
	return s
}

func StringInSlice(s string, slice []string) bool {
	for _, item := range slice {
		if s == item {
			return true
		}
	}
	return false
}

func RemoveDuplicates(slice []string) []string {
	seen := make(map[string]bool)
	result := []string{}
	for _, item := range slice {
		if !seen[item] {
			seen[item] = true
			result = append(result, item)
		}
	}
	return result
}