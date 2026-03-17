import re
import sys

def parse_markdown_to_sql(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    sql_statements = []
    
    current_table = None
    current_table_comment = ""
    columns = []
    constraints = []
    
    parsing_mode = None # "columns", "constraints", or None

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # New table starts usually with alphabet names followed by chinese parenthesis
        # e.g. "registries（注册中心表）" or "user_authentication 表（用户认证表）"
        # We need to ensure it's not "1.xxxx"
        table_match = re.match(r'^([a-zA-Z0-9_]+)(?:\s*表)?\s*[（(](.+?)[)）]$', line)
        if table_match and not "索引" in line and not "字段名" in line:
            if current_table:
                sql_statements.append(build_create_table(current_table, current_table_comment, columns, constraints))
            current_table = table_match.group(1)
            current_table_comment = table_match.group(2)
            columns = []
            constraints = []
            parsing_mode = None
            continue

        # Alternatively, sometimes Quartz tables like "QRTZ_JOB_DETAILS 表（作业详情表）"
        # The regex above catches it because it allows a-zA-Z0-9_
        
        if "字段名" in line and "类型" in line and "说明" in line:
            parsing_mode = "columns"
            continue
            
        if "索引与约束" in line:
            parsing_mode = None
            continue
            
        if "类型" in line and "名称" in line and "定义" in line:
            parsing_mode = "constraints"
            continue
            
        if "索引名称" in line and "字段组合" in line:
            # this is for index tables at the end, we can ignore
            parsing_mode = None
            current_table = None # stop collecting
            continue

        if parsing_mode == "columns":
            parts = re.split(r'\t', line)
            if len(parts) >= 5:
                name = parts[0].replace('\\_', '_').strip()
                ctype = parts[1].replace('\\_', '_').strip()
                nullable_str = parts[2].strip()
                default_val = parts[3].strip()
                comment = parts[4].replace("'", "''").strip()
                
                # clean ctype
                ctype = ctype.replace("CHARACTER SET utf8 COLLATE utf8_bin", "").strip()

                nullable = "NOT NULL" if "NOT NULL" in nullable_str.upper() else "NULL"
                
                # handle default
                if default_val in ["无", "", "NULL", "允许NULL"]:
                    default_str = ""
                elif default_val.lower() == "null":
                    default_str = "DEFAULT NULL"
                elif default_val.isdigit():
                    default_str = f"DEFAULT {default_val}"
                else:
                    default_val = default_val.replace("'", "''")
                    default_str = f"DEFAULT '{default_val}'"
                
                columns.append(f"  `{name}` {ctype} {nullable} {default_str} COMMENT '{comment}'")
                
        elif parsing_mode == "constraints":
            parts = re.split(r'\t', line)
            if len(parts) >= 3:
                ctype = parts[0].strip()
                cname = parts[1].replace('\\_', '_').strip()
                cdef = parts[2].replace('\\_', '_').strip()
                
                if "主键" in ctype or "PRIMARY" in ctype.upper():
                    if "(" in cdef:
                        cols = cdef.strip()
                    else:
                        cols = f"(`{cdef.strip()}`)"
                    cols = re.sub(r'（.*?）', '', cols)
                    constraints.append(f"  PRIMARY KEY {cols}")
                elif "唯一" in ctype or "UNIQUE" in ctype.upper():
                    if "(" in cdef:
                        cols = cdef.strip()
                    else:
                        cols = f"(`{cdef.strip()}`)"
                    cols = re.sub(r'（.*?）', '', cols)
                    cname = re.sub(r'（.*?）', '', cname)
                    constraints.append(f"  UNIQUE KEY `{cname}` {cols}")
                elif "索引" in ctype or "KEY" in ctype.upper() or "idx" in cname.lower() or "普通" in ctype:
                    if "(" in cdef:
                        cols = cdef.strip()
                    else:
                        cols = f"(`{cdef.strip()}`)"
                    cols = re.sub(r'（.*?）', '', cols)
                    constraints.append(f"  KEY `{cname}` {cols}")

    if current_table:
        sql_statements.append(build_create_table(current_table, current_table_comment, columns, constraints))

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(sql_statements))

def build_create_table(table, comment, columns, constraints):
    lines = [f"DROP TABLE IF EXISTS `{table}`;", f"CREATE TABLE `{table}` ("]
    inner_lines = columns + constraints
    lines.append(",\n".join(inner_lines))
    lines.append(f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='{comment}';")
    return "\n".join(lines)

if __name__ == "__main__":
    parse_markdown_to_sql(sys.argv[1], sys.argv[2])
