# Unbound-DNS-Management-API
This project is a Unbound DNS Management API developed using Flask, Gunicorn, and Nginx. It provides a REST-like API to manage the Unbound DNS server, allowing you to list, add, edit, and delete DNS records.

🚀 **Features**
- ✅ Manage DNS records: Add, edit, delete, and list records  
- ✅ Validation for IPv4/IPv6 and PTR records  
- ✅ Optimized deployment with Gunicorn and Nginx  
- ✅ Easy-to-use Flask REST API  
- ✅ Fully compatible with Unbound DNS
  
📌 **Installation**
- 1️⃣ **Install required dependencies**  
  ```sudo apt update && sudo apt install python3-flask gunicorn nginx -y```
  
- 2️⃣ **Set up Gunicorn as a service**  
  To keep Gunicorn running as a service, create the following systemd service file:  
  ```sudo nano /etc/systemd/system/unbound_api.service```
  
📌 **Set the content as follows:**  
   ~~~
      [Unit]  
      Description=Unbound Management API  
      After=network.target  

      [Service]  
      User=$USER  
      Group=$USER  
      WorkingDirectory=$PATH_TO_PROJECT  
      ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5000 unbound_management:app  
      Restart=always  

      [Install]  
      WantedBy=multi-user.target
   ~~~
  📌 **Enable and start the service:**
   ~~~
      sudo systemctl daemon-reload
      sudo systemctl enable unbound_api
      sudo systemctl start unbound_api
   ~~~
- 3️⃣ **Configure Nginx to proxy requests to Gunicorn**  
  ```sudo nano /etc/nginx/sites-available/unbound_api```

- 4️⃣ **Create Required Configuration Files**
  The code requires two configuration files under `/etc/unbound/unbound.conf.d/`.
  These files must include a server: section:
  
  `sudo nano /etc/unbound/unbound.conf.d/local_data.conf`

  `sudo nano /etc/unbound/unbound.conf.d/local_zone.conf`

📌 **Set the both files content as follows:**  

  `server:`  
  
📌 **Set correct file ownership and permissions:**  

~~~
  sudo chown root:$USER /etc/unbound/unbound.conf.d/local_data.conf /etc/unbound/unbound.conf.d/local_zone.conf
  sudo chmod 660 /etc/unbound/unbound.conf.d/local_data.conf /etc/unbound/unbound.conf.d/local_zone.conf
~~~
  
📌 **Set the content as follows:**
  ~~~
   server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
  }
  ~~~
📌 **Enable Nginx and restart:**
  ~~~
     sudo ln -s /etc/nginx/sites-available/unbound_api /etc/nginx/sites-enabled/
     sudo systemctl restart nginx
  ~~~


  🔗 **API Usage**

📌 **Add a DNS Record**  

  ~~~
     curl -X POST "http://localhost:5000/dns_config" \
     -d "action=ADD&content_type=data&record_type=A&domain_name=example.com&value=192.168.1.1"
  ~~~  
📌 **List DNS Records**  

  ```curl -X POST "http://localhost:5000/dns_config" -d "action=LIST&content_type=data"```  
  
📌 **Delete a DNS Record**  

  ~~~
    curl -X POST "http://localhost:5000/dns_config" \
     -d "action=REMOVE&content_type=data&remove_line=local-data: 'example.com 192.168.1.1'"
  ~~~

📌 **Edit a DNS Record**  

~~~
  curl -X POST "http://localhost:5000/dns_config" \
  -d "action=EDIT&content_type=data&remove_line=local-data: 'example.com 192.168.1.1'&new_line=local-data: 'example.com 192.168.1.2'"
~~~

📌 **Record Type & Required Parameters**  


| record_type   | Required Parameters                                      |  
|---------------|----------------------------------------------------------|  
| `A`           | domain_name, record_type, value                          |  
| `AAAA`        | domain_name, record_type, value                          |  
| `MX`          | domain_name, record_type, priority, value                |  
| `TXT`         | domain_name, record_type, text                           |  
| `PTR`         | pointer_domain, record_type, domain_name                 |  
| `CNAME`       | domain_name, record_type, alias_name                     |  
| `NS`          | domain_name, record_type, nameserver                     |  
| `SOA`         | domain_name, record_type, mname, rname, serial, refresh, |  
|               |  retry, expire, minimum                                  |  
| `ZONE`        | domain_name, zone_type                                   |  

⚠️ **Security Notes**  

- `sudo` privileges may be required.
  
  Commands such as `unbound-checkconf` and `systemctl restart unbound` require `sudo` access.
  
- Set `sudo` permissions for `unbound` with:  
  
  ~~~
    echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/unbound-checkconf, /bin/systemctl restart unbound" \
    | sudo tee /etc/sudoers.d/unbound_api
  ~~~

📄 License  

 This project is licensed under the MIT License.
    
