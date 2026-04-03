package logger

import (
	"os"
	"path/filepath"
	"time"

	"github.com/sirupsen/logrus"
)

type Logger struct {
	logger *logrus.Logger
	file   *os.File
}

func NewLogger(name string, level string) *Logger {
	logger := logrus.New()

	switch level {
	case "debug":
		logger.SetLevel(logrus.DebugLevel)
	case "info":
		logger.SetLevel(logrus.InfoLevel)
	case "warn":
		logger.SetLevel(logrus.WarnLevel)
	case "error":
		logger.SetLevel(logrus.ErrorLevel)
	default:
		logger.SetLevel(logrus.InfoLevel)
	}

	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp:   true,
		TimestampFormat: "2006-01-02 15:04:05",
	})

	return &Logger{
		logger: logger,
	}
}

func (l *Logger) SetOutputFile(path string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}

	l.logger.SetOutput(file)
	l.file = file
	return nil
}

func (l *Logger) Debug(args ...interface{}) {
	l.logger.Debug(args...)
}

func (l *Logger) Debugf(format string, args ...interface{}) {
	l.logger.Debugf(format, args...)
}

func (l *Logger) Info(args ...interface{}) {
	l.logger.Info(args...)
}

func (l *Logger) Infof(format string, args ...interface{}) {
	l.logger.Infof(format, args...)
}

func (l *Logger) Warn(args ...interface{}) {
	l.logger.Warn(args...)
}

func (l *Logger) Warnf(format string, args ...interface{}) {
	l.logger.Warnf(format, args...)
}

func (l *Logger) Error(args ...interface{}) {
	l.logger.Error(args...)
}

func (l *Logger) Errorf(format string, args ...interface{}) {
	l.logger.Errorf(format, args...)
}

func (l *Logger) Fatal(args ...interface{}) {
	l.logger.Fatal(args...)
}

func (l *Logger) Fatalf(format string, args ...interface{}) {
	l.logger.Fatalf(format, args...)
}

func (l *Logger) WithFields(fields map[string]interface{}) *logrus.Entry {
	return l.logger.WithFields(fields)
}

func (l *Logger) Close() {
	if l.file != nil {
		l.file.Close()
	}
}

type LogEntry struct {
	Timestamp time.Time `json:"timestamp"`
	Level     string    `json:"level"`
	Message   string    `json:"message"`
	Fields    map[string]interface{} `json:"fields,omitempty"`
}