import re
import os
import subprocess
import ipaddress
from string import Template
from flask import Flask, request, jsonify

# Variables
dns_types = {"A","AAAA","TXT","SOA","CNAME","PTR","MX", "NS"}

zone_types = {"deny", "refuse", "static", "transparent", "redirect", "nodefault",
"typetransparent", "inform", "inform_deny", "inform_redirect", "always_transparent",
"block_a", "always_refuse", "always_nxdomain", "always_null", "noview"}

ctypes = {"data", "zones"}

act_types = {"ADD", "REMOVE", "LIST", "EDIT"}

allowed_params = {
    "action", "content_type", "zone_type", "record_type", "domain_name",
    "value", "priority", "remove_line", "new_line", "text", "ttl",
    "pointer_domain", "nameserver", "alias_name", "mname", "rname",
    "serial", "refresh", "retry", "expire", "minimum", "data", "zones"
    }

mandatory_params = ["record_type", "content_type", "domain_name"]
main_path = "/etc/unbound/unbound.conf.d/"
main_conf_file = "/etc/unbound/unbound.conf"

TEMPLATES = {
    "ZONE": "local-zone: '${domain_name}.' '${zone_type}'\n",
    "MX": "local-data: '${domain_name}. 3600 IN ${record_type} ${priority} ${value}'\n",
    "A": "local-data: '${domain_name}. 3600 IN ${record_type} ${value}'\n",
    "AAAA": "local-data: '${domain_name}. 3600 IN ${record_type} ${value}'\n",
    "TXT": "local-data: '${domain_name}. 3600 IN ${record_type} \"${text}.\"'\n",
    "PTR": "local-data-ptr: '${pointer_domain} ${domain_name}.'\n",
    "CNAME": "local-data: '${domain_name}. 3600 IN ${record_type} ${alias_name}.'\n",
    "NS": "local-data: '${domain_name}. 3600 IN ${record_type} ${nameserver}.'\n",
    "SOA": "local-data: '${domain_name}. 3600 IN ${record_type} ${mname} ${rname} ${serial} ${refresh} ${retry} ${expire} ${minimum}'\n"
}

DNS_FIELDS = {
    "A": ["domain_name", "record_type", "value"],
    "AAAA": ["domain_name", "record_type", "value"],
    "MX": ["domain_name", "record_type", "priority", "value"],
    "TXT": ["domain_name", "record_type", "text"],
    "PTR": ["pointer_domain", "record_type", "domain_name"],
    "CNAME": ["domain_name", "alias_name", "record_type"],
    "NS": ["domain_name", "record_type", "nameserver"],
    "SOA": ["domain_name", "record_type", "mname", "rname", "serial", "refresh", "retry", "expire", "minimum"],
    "ZONE": ["domain_name", "zone_type"]
    }

# Run system commands
def run_process(command):
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr
    except Exception as e:
        return None, str(e)

def check_and_restart(conf_file):
        # Configuration check
        check_output, check_error = run_process(["sudo", "unbound-checkconf", conf_file])
        if check_error:
            return f"Error: Configuration error.", 400
        # Service restart
        restart_output, restart_error = run_process(["sudo", "systemctl", "restart", "unbound.service"])
        if restart_error:
            return f"Error: Service could not be restarted!", 400 
        
# Parameter Check
def param_validation(params):
    missing = [param for param, value in params.items() if not value]
    return (f"Missing parameter: {', '.join(missing)}", False) if missing else ("", True)

# IP/IPv6 Validation
def ip_validation(record_type, address, **kwargs):
    try:
        if record_type == "A":
            ipaddress.IPv4Address(address)
        elif record_type == "AAAA":
            ipaddress.IPv6Address(address)
        elif record_type == "MX":
            ipaddress.ip_address(address)
        elif record_type == "PTR":
            pointer_domain = kwargs.get("pointer_domain", "").strip()
            try:
                ipaddress.ip_address(address)
                return False, f"Error: PTR record cannot have an IP address as domain name ({address})"
            except ValueError:
                try:
                    ip_obj = ipaddress.ip_address(pointer_domain)
                    if not isinstance(ip_obj, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
                        return False, f"Error: PTR record requires a valid IPv4 or IPv6 address as pointer domain ({pointer_domain})"
                except ValueError:
                    return False, f"Error: PTR record requires a valid IPv4 or IPv6 address as pointer domain ({pointer_domain})"
        else:
            return False, f"Invalid IP address for {record_type} record."

        return True, None
    except ValueError:
        return False, f"Invalid IP address: {address}"

# Add DNS Record
def dns_record_add(conf_file, record):
    with open(conf_file, "a") as file:
        file.write(record)
    return check_and_restart(conf_file) or ("Record added successfully!", 200)

# Erase Record
def delete_line(del_record, content_type):
    conf_file = f"{main_path}local_{content_type}.conf"
    with open(conf_file, "r") as dfile:
        lines = dfile.readlines()
    if del_record.strip() not in map(str.strip, lines):
        return f"{del_record} not found!", 400
    updated_lines = [line for line in lines if line.strip() != del_record.strip()]
    with open(conf_file, "w") as ufile:
        ufile.writelines(updated_lines)
    return check_and_restart(conf_file) or ("Record updated successfully!", 200)

# Record Edit
def edit_line(ed_line, cur_line, content_type):
    conf_file = f"{main_path}local_{content_type}.conf"
    if not os.path.exists(conf_file):
        return f"Error: Configuration file '{conf_file}' does not exist.", 400
    with open(conf_file, "r") as edfile:
        lines = edfile.readlines()
    stripped_lines = [line.strip() for line in lines]
    if cur_line.strip() not in stripped_lines:
        return f"{cur_line} not found.", 400
    updated_lines = [ed_line if line.strip() == cur_line.strip() else line for line in lines]
    with open(conf_file, "w") as ufile:
        ufile.writelines(updated_lines)
    return check_and_restart(conf_file) or ("Record updated successfully!", 200)

# Record generator:
def generate_record(record_type, params):
    template_str = TEMPLATES.get(record_type)
    if not template_str:
        return f"Error: {record_type} has no any template!"
    try:
        template = Template(template_str)
        return template.substitute(params), None
    except KeyError as e:
        return None, f"Error: Missing variable - {e}"

# Domain validator
def validate_domain(domain_name):
    domain_regex = re.compile(
        r'^(?!-)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$'
    )
    return bool(domain_regex.match(domain_name))

app = Flask(__name__)

@app.route('/dns_config', methods=['POST'])
def dns_config():
    action_type = request.form.get("action", "").upper()
    content_type = request.form.get("content_type", "").lower()
    record_type = request.form.get("record_type", "").upper()
    domain_name = request.form.get("domain_name", "")
    priority = request.form.get("priority", "")
    zone_type = request.form.get("zone_type", "")
    old_line = request.form.get("remove_line", "")
    new_line = request.form.get("new_line", "")
    
    params = {key: request.form.get(key) for key in allowed_params}
    locals().update(params)
    DNSs = {record: {field: params.get(field) for field in fields} for record, fields in DNS_FIELDS.items()}

    if action_type not in act_types:
        return jsonify({"error": "Invalid Action!"}), 400
    if content_type not in ctypes:
        print(content_type)
        return jsonify({"error": "Invalid Content Type"}), 400

# List records
    if action_type == "LIST":
        conf_path = f"list_local_{content_type}"
        output, error = run_process(["sudo", "unbound-control", conf_path])
        if error:
            return jsonify({"error": error}), 500
        filtered_output = re.findall(r".+", output, re.MULTILINE)
        return jsonify({"output": filtered_output}), 200
    
# Add Record
    if action_type == "ADD":
        if (record_type in dns_types and content_type == "data") or (record_type == "ZONE" and content_type == "zones"):
            params_filtered = {key: value for key, value in DNSs.get(record_type, {}).items()}
            error_message, valid = param_validation(params_filtered)
            if not valid:
                return jsonify({"error": error_message}), 400
            # domain name validation
            if not validate_domain(domain_name):
                return jsonify({"error": f"Invalid domain name '{domain_name}'"}), 400
            if zone_type and (not zone_type in zone_types):
                return jsonify({"error": "Unknown zone type!"}), 400
            # priority validation
            if priority and (not priority.isdigit() or not (0 <= int(priority) <= 65535)):
                return jsonify({"error": "Priority must be a number and must be between 0 and 65535."}), 400
            # ip validation
            if record_type in {"A", "AAAA", "MX"}:
                valid, invalid = ip_validation(record_type, params.get("value", ""))
                if not valid:
                    return jsonify({"error": invalid}), 400
            if record_type == "PTR":
                valid, invalid = ip_validation(record_type, domain_name, pointer_domain=params.get("pointer_domain", ""))
                if not valid:
                    return jsonify({"error": invalid}), 400
            record, fail = generate_record(record_type, params_filtered)
            if fail:
                return jsonify({"error": fail}), 400
            # set file path
            conf_path = f"{main_path}local_{content_type}.conf"
            # check if file exist
            if not os.path.exists(conf_path):
                return jsonify({"error": f"Configuration file '{conf_path}' does not exist."}), 400
            return dns_record_add(conf_path, record)
        else:
            return jsonify({"error": "Unknown combination!"})

# Remove record
    if action_type == "REMOVE":
        if not old_line:
            return jsonify({"error": "Record cannot be empty!"}), 400
        if content_type == "zones":
            old_line_parts = old_line.split()
            if len(old_line_parts) != 2:
                return jsonify({"error": "Invalid zone format!"}), 400
            old_line = f"local-zone: '{old_line_parts[0]}' '{old_line_parts[1]}'"
        elif content_type == "data":
            old_line = f"local-data: '{old_line}'"
        else:
            return jsonify({"error": "Unknown content type! '{content_type}'"})
        return delete_line(old_line, content_type)

# Record edit
    if action_type == "EDIT" and params.get("content_type") in ctypes:
        record_type = params.get("record_type")
        old_line = params.get("remove_line")
        new_line = params.get("new_line")
        if not old_line or not new_line:
            return jsonify({"error": "Old and new records cannot be empty!"}), 400
        content_type = params.get("content_type")
        if content_type == "zones":
            old_line_parts = old_line.split()
            new_line_parts = new_line.split()
            if len(old_line_parts) < 2 or len(new_line_parts) < 2:
                return jsonify({"error": "Invalid zone format!"}), 400
            cur_line = f"local-zone: '{old_line_parts[0]}' '{old_line_parts[1]}'"
            ed_line = f"local-zone: '{new_line_parts[0]}.' '{new_line_parts[1]}'"
        else:
            cur_line = f"local-data: '{old_line}'"
            new_line_parts = new_line.split()
            if record_type in {"A", "AAAA", "MX"}:
                ip_address = new_line_parts[-1]
                valid_ip, invalid_ip = ip_validation(record_type, ip_address)
            if not valid_ip:
                return jsonify({"error": f"Invalid IP address: {invalid_ip}"}), 400
            if record_type == "MX":
                priority = new_line_parts[-2]
                if not priority.isdigit() or not (0 <= int(priority) <= 65535):
                    return jsonify({"error": "Priority must be a number and between 0 and 65535."}), 400
            ed_line = f"local-data: '{new_line}'"
        return edit_line(ed_line, cur_line, content_type)

if __name__ == "__main__":
    app.run()
