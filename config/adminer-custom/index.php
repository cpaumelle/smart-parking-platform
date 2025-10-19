<!DOCTYPE html>
<html lang="en">
<head>
   <meta charset="UTF-8">
   <meta name="viewport" content="width=device-width, initial-scale=1.0">
   <title>Smart Parking Database Shortcuts</title>
   <style>
       body { font-family: Arial, sans-serif; margin: 2em; background: #f5f5f5; }
       .container { max-width: 600px; margin: 0 auto; background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
       h1 { color: #333; text-align: center; }
       .db-link { display: block; padding: 1em; margin: 1em 0; background: #e3f2fd; border-radius: 5px; text-decoration: none; color: #1976d2; }
       .db-link:hover { background: #bbdefb; }
       .desc { font-size: 0.9em; color: #666; }
   </style>
</head>
<body>
   <div class="container">
       <h1>Database Shortcuts</h1>

       <a href="adminer.php?pgsql=postgres&username=parking_user&db=parking_v2" class="db-link">
           <strong>Parking v5 Database</strong><br>
           <span class="desc">New v5 application database</span>
       </a>

       <a href="adminer.php?pgsql=postgres&username=parking_user&db=chirpstack" class="db-link">
           <strong>ChirpStack Database</strong><br>
           <span class="desc">LoRaWAN network server data</span>
       </a>

       <a href="adminer.php?pgsql=postgres&username=parking_user&db=parking_platform" class="db-link">
           <strong>Parking v4 Database (Legacy)</strong><br>
           <span class="desc">Old v4 data for migration</span>
       </a>

       <hr style="margin: 2em 0;">
       <a href="adminer.php" style="color: #666; font-size: 0.9em;">Standard Adminer Login</a>
   </div>
</body>
</html>
