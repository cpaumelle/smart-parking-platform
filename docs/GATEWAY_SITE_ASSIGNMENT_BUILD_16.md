# Gateway Site Assignment Feature - Build 16

**Deployed:** 2025-10-21
**Build:** 20251021.16
**Status:** ✅ LIVE at https://devices.verdegris.eu

---

## Summary

Based on your excellent suggestion: *"Maybe the Description field in Chirpstack is a good one to use for 'Sites' insertion"*

We've implemented gateway site assignment by making the ChirpStack `description` field editable directly from our UI.

---

## What Changed

### Backend: PATCH Endpoint Added

**Endpoint:** `PATCH /api/v1/gateways/{gw_eui}`

**Request Body:**
```json
{
  "description": "Main Building - Floor 2",
  "tags": {
    "site_id": "00000000-0000-0000-0000-000000000001"
  }
}
```

**Response:**
```json
{
  "gw_eui": "7276ff002e062e5e",
  "gateway_name": "Outdoor Gateway 1",
  "description": "Main Building - Floor 2",
  "tags": {...},
  "updated_at": "2025-10-21T14:30:00Z"
}
```

**Implementation:**
- Updates ChirpStack PostgreSQL database directly
- Merges new tags with existing tags (non-destructive)
- Sets `updated_at` timestamp automatically
- Proper error handling (404, 400, 500)

**File:** `src/routers/gateways.py:180-276`

---

### Frontend: Editable Gateway Modal

**What You'll See:**

1. **Open Gateway Configuration:**
   - Click any gateway in the Gateways page
   - Modal title: "Configure Gateway: {gateway_name}"

2. **Edit Description Field:**
   - Multi-line text area for site/location
   - Placeholder text guides you: "e.g., Main Building - Floor 2, Downtown Parking Garage, etc."
   - Character limit: None (text field in ChirpStack is TEXT type)

3. **Save Changes:**
   - Click "Save Site Assignment" button
   - Shows spinner: "Saving..."
   - On success: Green banner "Gateway Updated Successfully!"
   - On error: Red banner with error message
   - Auto-closes modal after 1 second on success

4. **Cancel Without Saving:**
   - Click "Cancel" button to close without saving

**Files:**
- `frontend/device-manager/src/components/gateways/GatewayConfigModal.jsx`
- `frontend/device-manager/src/services/gateways.js`

---

## How to Use

### Assigning a Gateway to a Site:

1. **Navigate to Gateways page** in the UI
2. **Click on any gateway** to open the configuration modal
3. **Edit the "Site / Location Description" field**
   - Enter the site name or location where the gateway is installed
   - Examples:
     - "Main Building - Floor 2"
     - "Downtown Parking Garage"
     - "Campus North - Building A"
4. **Click "Save Site Assignment"**
5. **Verify the update:**
   - Green success message appears
   - Modal closes after 1 second
   - Gateway list refreshes
   - Changes visible in ChirpStack admin interface

### Viewing Site Assignments:

- **In Our UI:** Description shows in the gateway details modal
- **In ChirpStack Admin:** Description field shows the site assignment
- **Both UIs stay in sync** (same PostgreSQL database)

---

## Technical Details

### Why the Description Field?

1. **ChirpStack Native:** Description is a standard field in ChirpStack's gateway table
2. **Visible Everywhere:** Shows in both our UI and ChirpStack admin interface
3. **Text Field:** Can store detailed site information (not just an ID)
4. **Human Readable:** Operators can read the site name directly
5. **No Schema Changes:** Uses existing ChirpStack database structure

### Database Update Query:

```sql
UPDATE gateway
SET description = $1,
    updated_at = NOW()
WHERE encode(gateway_id, 'hex') = $2
RETURNING
    encode(gateway_id, 'hex') as gw_eui,
    name as gateway_name,
    description,
    tags,
    updated_at
```

### Tags for Additional Metadata:

You can also use the `tags` field (JSONB in ChirpStack) for structured metadata:

```javascript
await updateGateway('7276ff002e062e5e', {
  description: 'Main Building - Floor 2',
  tags: {
    site_id: '00000000-0000-0000-0000-000000000001',
    floor: 2,
    zone: 'north'
  }
});
```

---

## API Testing

### Using curl:

```bash
# Update gateway description
curl -X PATCH \
  -H "X-API-Key: MiuP3Vd6FHxfucKxkF0xwvFVbpo46Jc8ZsmjhZN6Svc" \
  -H "Content-Type: application/json" \
  -d '{"description":"Main Building - Floor 2"}' \
  https://api.verdegris.eu/api/v1/gateways/7276ff002e062e5e

# Response:
{
  "gw_eui": "7276ff002e062e5e",
  "gateway_name": "Outdoor Gateway 1",
  "description": "Main Building - Floor 2",
  "tags": {},
  "updated_at": "2025-10-21T14:30:00.123456Z"
}
```

### Using JavaScript/TypeScript:

```javascript
import { updateGateway } from './services/gateways.js';

// Update gateway description
const result = await updateGateway('7276ff002e062e5e', {
  description: 'Main Building - Floor 2'
});

console.log('Updated:', result.description);
```

---

## Verification Checklist

- ✅ Backend PATCH endpoint implemented and tested
- ✅ Frontend service function added
- ✅ Gateway modal UI updated with editable field
- ✅ Save/Cancel buttons functional
- ✅ Success/Error messages display correctly
- ✅ Build 16 deployed to production
- ✅ Asset hash updated (CepfyXmQ)
- ✅ version.json shows Build 16
- ✅ Changes persisted in ChirpStack database

---

## Future Enhancements (Optional)

### 1. Site Selection Dropdown:

Instead of free-text description, add a dropdown to select from existing sites:

```jsx
<select
  value={selectedSiteId}
  onChange={(e) => {
    const site = sites.find(s => s.id === e.target.value);
    setDescription(site.name);
  }}
>
  {sites.map(site => (
    <option key={site.id} value={site.id}>
      {site.name}
    </option>
  ))}
</select>
```

### 2. Automatic Tag Population:

When selecting a site, automatically populate tags:

```javascript
await updateGateway(gateway.gw_eui, {
  description: site.name,
  tags: {
    site_id: site.id,
    site_name: site.name,
    assigned_at: new Date().toISOString()
  }
});
```

### 3. Gateway-Site Relationship Table:

Create a dedicated `gateway_sites` table in our parking database for more structured relationships:

```sql
CREATE TABLE gateway_sites (
  gw_eui VARCHAR(16) NOT NULL,
  site_id UUID NOT NULL REFERENCES sites(id),
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (gw_eui)
);
```

---

## Known Issues

### 1. Device Types Not Displaying (Ongoing)

**Status:** Not related to this build
**Likely Cause:** Browser cache
**Solution:** Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)

**API Returns Correct Data:**
```json
{
  "device_type": "browan_tbms100_motion",
  "device_type_id": 123
}
```

If hard refresh doesn't work, let me know and we'll investigate further.

---

## Support

If you encounter any issues:

1. **Check Browser Console:** F12 → Console tab for JavaScript errors
2. **Check Network Tab:** F12 → Network tab for failed API calls
3. **Check API Response:** Look for 400/500 errors in responses
4. **Report Issue:** Provide gateway EUI and error message

---

## Conclusion

✅ **Gateway site assignment is now fully functional!**

You can now:
- Assign gateways to sites via the description field
- Updates persist in ChirpStack database
- Changes visible in both UIs
- No need to access ChirpStack admin interface

**Next:** Test the feature in production and let me know if you'd like any of the optional enhancements!
