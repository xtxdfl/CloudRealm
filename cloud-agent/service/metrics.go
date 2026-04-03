package service

import (
	"os/exec"
	"runtime"
	"strconv"
	"strings"
)

func GetMemoryTotal() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "OS", "get", "TotalVisibleMemorySize", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "TotalVisibleMemorySize") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						return val * 1024
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "free -b 2>/dev/null | awk '/Mem:/ {print $2}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 8 * 1024 * 1024 * 1024
}

func GetMemoryUsed() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "OS", "get", "FreePhysicalMemory", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "FreePhysicalMemory") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						total := GetMemoryTotal()
						return total - (val * 1024)
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "free -b 2>/dev/null | awk '/Mem:/ {print $3}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 4 * 1024 * 1024 * 1024
}

func GetDiskTotal() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "logicaldisk", "get", "size", "/value")
		output, _ := cmd.Output()
		var total int64
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "Size=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						total += val
					}
				}
			}
		}
		if total > 0 {
			return total
		}
	}
	cmd := exec.Command("sh", "-c", "df -B1 2>/dev/null | awk 'NR>1 {sum+=$2} END {print sum}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 100 * 1024 * 1024 * 1024
}

func GetDiskUsed() int64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "logicaldisk", "get", "size,freespace", "/value")
		output, _ := cmd.Output()
		var totalSize, freeSize int64
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "Size=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						totalSize += val
					}
				}
			}
			if strings.Contains(line, "FreeSpace=") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64); err == nil {
						freeSize += val
					}
				}
			}
		}
		if totalSize > 0 {
			return totalSize - freeSize
		}
	}
	cmd := exec.Command("sh", "-c", "df -B1 2>/dev/null | awk 'NR>1 {sum+=$3} END {print sum}'")
	output, err := cmd.Output()
	if err == nil {
		if val, err := strconv.ParseInt(strings.TrimSpace(string(output)), 10, 64); err == nil {
			return val
		}
	}
	return 50 * 1024 * 1024 * 1024
}

func GetCPUUsage() float64 {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "cpu", "get", "loadpercentage", "/value")
		output, _ := cmd.Output()
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "LoadPercentage") {
				parts := strings.Split(line, "=")
				if len(parts) > 1 {
					if val, err := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64); err == nil {
						return val
					}
				}
			}
		}
	}
	cmd := exec.Command("sh", "-c", "top -bn1 | grep 'Cpu' | awk '{print $2}' | cut -d'%' -f1")
	output, err := cmd.Output()
	if err == nil {
		outputStr := strings.TrimSpace(string(output))
		if outputStr != "" {
			outputStr = strings.ReplaceAll(outputStr, ",", ".")
			if val, err := strconv.ParseFloat(outputStr, 64); err == nil {
				return val
			}
		}
	}
	return 0.0
}