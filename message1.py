def run_terraform_apply(folder_name):
    subprocess.call(['terraform', 'init'], cwd=folder_name)
    terraform_apply_result = subprocess.call(['terraform', 'apply', '-auto-approve', '-input=false'], cwd=folder_name)

    if terraform_apply_result == 0:
        print(f"Terraform apply succeeded for folder {folder_name}")
    else:
        print(f"Terraform apply failed for folder {folder_name}")







def start_warm_instance_and_run_commands():
    ec2 = boto3.resource('ec2')
    instances = ec2.instances.filter(
        Filters=[{'Name': 'tag:state', 'Values': ['warm']}]
    )

    warm_instance = None
    for instance in instances:
        if instance.state['Name'] == 'stopped':
            warm_instance = instance
            break

    if warm_instance:
        warm_instance.start()
        warm_instance.wait_until_running()

        # Replace with the private key file path corresponding to the started instance
        key = paramiko.RSAKey.from_private_key_file('/home/ubuntu/boto3/terraform/terraform-key-pair')
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Replace 'ubuntu' with the appropriate user for your instance
        ssh_client.connect(hostname=warm_instance.public_ip_address, username='ubuntu', pkey=key)

        commands = [
            'cd /home/ubuntu/listener && python3 warm.py'
        ]

        for command in commands:
            stdin, stdout, stderr = ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                print(f"Error executing command {command}: {stderr.read().decode('utf-8')}")

        ssh_client.close()
        return True
    else:
        return False



@app.route('/api/v1/instance/create', methods=['POST'])
def terraform_apply():
    api_key = request.headers.get('x-api-key')
    if api_key != API_KEY:
        response = {
            "message": {
                "message": "Invalid API key",
                "success_status": False
            }
        }
        return app.response_class(json.dumps(response), status=401, mimetype='application/json')

    def start_warm_instance_thread():
        # Check if there is a warm instance available
        warm_instance_started = start_warm_instance_and_run_commands()

        if warm_instance_started:
            response = {
                "message": {
                    "message": "Warm instance startup process initiated",
                    "success_status": True
                }
            }
            return app.response_class(json.dumps(response), status=200, mimetype='application/json')
        else:
            # If no warm instance is available, execute the rest of the code here
            # ...
            # (rest of the code)

    warm_instance_thread = threading.Thread(target=start_warm_instance_thread)
    warm_instance_thread.start()

    response = {
        "message": {
            "message": "Request submitted",
            "success_status": True
        }
    }
    return app.response_class(json.dumps(response), status=200, mimetype='application/json')





    request_data = json.loads(request.data.decode('utf-8'))
    instance_id = request_data.get('instance_id')
    machine_type = request_data.get('machine_type') or 'g3s.xlarge'
    app_type = request_data.get('app')
    ami = request_data.get('ami')

    # Define the stable and automat variables
    stable = os.getenv("STABLE_DIR_NAME")
    automat = os.getenv("AUTOMATIC_DIR_NAME")

    # Define the cmd-stable and cmd-vlad variables
    cmd_stable = os.getenv("RUN_A1111")
    cmd_vlad = os.getenv("RUN_VLAD")
    efs_vlad = os.getenv("EFS_VLAD_PATH")
    ctn_auto_path = os.getenv("CONTROL_NET_AUTO_EFS_PATH")
    ctn_vlad_path = os.getenv("CONTROL_NET_VLAD_EFS_PATH")
    efs_auto = os.getenv("EFS_A1111_PATH")
    env_tag = os.getenv("ENV_TAG")
    app_name_a1111 = os.getenv("APP_NAME_A1111")
    app_name_vlad = os.getenv("APP_NAME_VLAD")
    if app_type == app_name_a1111:
        path = stable
        cmd = cmd_stable
        efs = efs_auto
        control_net = ctn_auto_path
    elif app_type == app_name_vlad:
        path = automat
        cmd = cmd_vlad
        efs = efs_vlad
        control_net = ctn_vlad_path 
    else:
        # Handle cases when the app value is neither 'a1111' nor 'vlad'
        response = {
            "message": {
                "message": "Invalid app value",
                "success_status": False
            }
        }
        return app.response_class(json.dumps(response), status=400, mimetype='application/json')


    folder_name = f"users/{instance_id}"
    os.makedirs(folder_name, exist_ok=True)
    subprocess.call(['cp', f"{terraform_dir}/{code_file}", f"{folder_name}/{code_file}"])
    subprocess.call(['cp', f"{terraform_dir}/terraform-key-pair", f"{folder_name}/terraform-key-pair"])
    with open(f"{folder_name}/{code_file}", 'r') as file:
        filedata = file.read()
    subdomain_pattern = re.compile(r'(subdomain[0-9]+)')
    filedata = filedata.replace('instance_type = "g3s.xlarge"', f'instance_type = "{machine_type}"')
    filedata = filedata.replace('ami           = "ami-08befd361c3f6f2e7"', f'ami           = "{ami}"')
    filedata = filedata.replace('  default = "thinkfusion-instance"', f'  default = "{instance_id}"')
    filedata = re.sub(r"\bsubdomain\b", instance_id, filedata)
    filedata = re.sub(r"\bapp-type\b", app_type, filedata)
    filedata = re.sub(r"\bPATH\b", path, filedata)
    filedata = re.sub(r"\bcommand-run\b", cmd, filedata)
    filedata = re.sub(r"\bdev\b", env_tag, filedata)
    filedata = re.sub(r"\befs-path\b", efs, filedata)
    filedata = re.sub(r"\bweb_hook_url_replace\b", WEB_HOOKURL_URL, filedata)
    filedata = re.sub(r"\bweb_hook_api_key_replace\b", WEB_HOOK_API_KEY, filedata)
    filedata = re.sub(r"\bControl_Net_PATH\b", control_net, filedata)
    with open(f"{folder_name}/{code_file}", 'w') as file:
        file.write(filedata)

    response = {
        "message": {
            "message": "Successfully submitted request",
            "success_status": True,
            "machine_type": machine_type,
            "instance_id" : instance_id,
            "app"         : app_type
        }
    }
    response_thread = threading.Thread(target=lambda: app.response_class(json.dumps(response), status=200, mimetype='application/json').response)
    response_thread.start()
    terraform_thread = threading.Thread(target=run_terraform_apply, args=(folder_name,))
    terraform_thread.start()
    return app.response_class(json.dumps(response), status=202, mimetype='application/json')
