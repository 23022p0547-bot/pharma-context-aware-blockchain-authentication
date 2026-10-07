# Pharma lifecycle bulk-load package

Matches the uploaded PharmaDrugAuthentication project.

Dataset:
- 1,000 unique products
- 3,000 sequential transfers
- Manufacturer -> Distributor -> Wholesaler -> Retail Outlet
- QR hash exactly matches backend/app.py:
  drugID|drugName|manufacturer|batchNumber|manufactureDate|expiryDate

Recommended pilot:
1. Start Fabric network/chaincode, Node gateway (port 3000), and optionally Flask dashboard.
2. Copy this package into PharmaDrugAuthentication/experiments/.
3. cd experiments
4. python3 bulk_register_1000.py --limit 10
5. Confirm the 10 drugs in the dashboard/API.
6. python3 bulk_transfer_3000.py --limit 15
   This tests 5 products x 3 sequential transfers.
7. python3 validate_provenance.py --limit 5

Clean final experiment (after resetting the test ledger):
1. python3 bulk_register_1000.py
2. python3 bulk_transfer_3000.py
3. python3 validate_provenance.py

Do not manually insert lifecycle rows into CouchDB. The scripts use your existing
POST /drugs and POST /drugs/:drugId/transfer routes so the operations are actual
Fabric transactions.

Output files:
- registration_results.csv
- transfer_results.csv
- provenance_validation.csv
