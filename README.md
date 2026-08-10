# TicketPulse — PostgreSQL edition

This application stores manager, staff, daily report, pending task, critical flag, manager remark, and follow-up date data in PostgreSQL.

## Free Render deployment

This repository includes `render.yaml`, which creates both the Node.js web service and a Render PostgreSQL database.

1. Push this folder to your GitHub repository.
2. Create or sign in to a [Render account](https://render.com/).
3. In Render, select **New → Blueprint**, connect the GitHub repository, and select `render.yaml`.
4. Confirm the service and database, both on the **Free** plan, then click **Apply**.
5. When the deployment completes, open the service URL shown by Render:
   - `/manager.html` for managers
   - `/staff.html` for staff

The build command automatically runs `database.sql` against the Render PostgreSQL database on each deploy.

> Important: Render’s free PostgreSQL database is a trial/pilot option. It expires after 30 days and has no backups. Export the data before expiry or upgrade to a paid database for any live business use.

## Local set up

1. Create a PostgreSQL database named `ticketpulse` (or use a managed provider such as Supabase, Neon, AWS RDS, or Render PostgreSQL).
2. Run `database.sql` against that database.
3. Copy `.env.example` to `.env` and set `DATABASE_URL`.
4. Install Node.js dependencies: `npm install`.
5. Start the application: `npm start`.
6. Open `http://localhost:3000/manager.html` or `http://localhost:3000/staff.html`.

For cloud deployment, host this Node app on a service that supports long-running Node processes, set `DATABASE_URL` as a secure environment variable, and run the schema migration before going live. Do not put database passwords in the HTML or JavaScript files.
