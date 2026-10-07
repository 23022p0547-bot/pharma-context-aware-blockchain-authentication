package main

// Drug represents one pharmaceutical product recorded on the blockchain.
type Drug struct {
	DrugID          string `json:"drugID"`
	DrugName        string `json:"drugName"`
	Manufacturer    string `json:"manufacturer"`
	BatchNumber     string `json:"batchNumber"`
	ManufactureDate string `json:"manufactureDate"`
	ExpiryDate      string `json:"expiryDate"`
	CurrentOwner    string `json:"currentOwner"`
	Status          string `json:"status"`
	QRHash          string `json:"qrHash"`
	OwnershipHash   string `json:"ownershipHash"`
	CreatedAt       string `json:"createdAt"`
	UpdatedAt       string `json:"updatedAt"`
}

// VerificationResult represents the result returned during drug verification.
type VerificationResult struct {
	DrugID  string `json:"drugID"`
	IsValid bool   `json:"isValid"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

// DrugHistory represents one historical ledger modification.
type DrugHistory struct {
	TxID      string `json:"txID"`
	Timestamp string `json:"timestamp"`
	IsDeleted bool   `json:"isDeleted"`
	Drug      *Drug  `json:"drug,omitempty"`
}
