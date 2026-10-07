package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// SmartContract provides functions for managing pharmaceutical drugs.
type SmartContract struct {
	contractapi.Contract
}

// computeOwnershipHash creates a deterministic SHA-256 hash
// for the pharmaceutical ownership chain.
func computeOwnershipHash(parts ...string) string {

	data := strings.Join(parts, "|")

	hash := sha256.Sum256([]byte(data))

	return hex.EncodeToString(hash[:])
}

// RegisterDrug adds a new drug record to the blockchain.
func (s *SmartContract) RegisterDrug(
	ctx contractapi.TransactionContextInterface,
	drugID string,
	drugName string,
	manufacturer string,
	batchNumber string,
	manufactureDate string,
	expiryDate string,
	currentOwner string,
	qrHash string,
) error {

	drugID = strings.TrimSpace(drugID)

	if drugID == "" {
		return fmt.Errorf("drug ID cannot be empty")
	}

	exists, err := s.DrugExists(ctx, drugID)
	if err != nil {
		return err
	}

	if exists {
		return fmt.Errorf("drug %s already exists", drugID)
	}

	txTime, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to obtain transaction timestamp: %v", err)
	}

	timestamp := time.Unix(txTime.Seconds, int64(txTime.Nanos)).
		UTC().
		Format(time.RFC3339)

	initialOwnershipHash := computeOwnershipHash(
		drugID,
		strings.TrimSpace(qrHash),
		strings.TrimSpace(currentOwner),
	)

	drug := Drug{
		DrugID:          drugID,
		DrugName:        strings.TrimSpace(drugName),
		Manufacturer:    strings.TrimSpace(manufacturer),
		BatchNumber:     strings.TrimSpace(batchNumber),
		ManufactureDate: strings.TrimSpace(manufactureDate),
		ExpiryDate:      strings.TrimSpace(expiryDate),
		CurrentOwner:    strings.TrimSpace(currentOwner),
		Status:          "ACTIVE",
		QRHash:          strings.TrimSpace(qrHash),
		OwnershipHash:   initialOwnershipHash,
		CreatedAt:       timestamp,
		UpdatedAt:       timestamp,
	}

	drugJSON, err := json.Marshal(drug)
	if err != nil {
		return fmt.Errorf("failed to serialize drug record: %v", err)
	}

	return ctx.GetStub().PutState(drugID, drugJSON)
}

// ReadDrug retrieves a drug record using its drug ID.
func (s *SmartContract) ReadDrug(
	ctx contractapi.TransactionContextInterface,
	drugID string,
) (*Drug, error) {

	drugJSON, err := ctx.GetStub().GetState(drugID)
	if err != nil {
		return nil, fmt.Errorf("failed to read drug %s: %v", drugID, err)
	}

	if drugJSON == nil {
		return nil, fmt.Errorf("drug %s does not exist", drugID)
	}

	var drug Drug

	if err := json.Unmarshal(drugJSON, &drug); err != nil {
		return nil, fmt.Errorf("failed to deserialize drug %s: %v", drugID, err)
	}

	return &drug, nil
}

// DrugExists checks whether a drug ID is already present in the ledger.
func (s *SmartContract) DrugExists(
	ctx contractapi.TransactionContextInterface,
	drugID string,
) (bool, error) {

	drugJSON, err := ctx.GetStub().GetState(drugID)
	if err != nil {
		return false, fmt.Errorf("failed to check drug %s: %v", drugID, err)
	}

	return drugJSON != nil, nil
}

// GetAllDrugs returns every drug record stored in the ledger.
func (s *SmartContract) GetAllDrugs(
	ctx contractapi.TransactionContextInterface,
) ([]*Drug, error) {

	resultsIterator, err := ctx.GetStub().GetStateByRange("", "")
	if err != nil {
		return nil, fmt.Errorf("failed to retrieve drug records: %v", err)
	}
	defer resultsIterator.Close()

	var drugs []*Drug

	for resultsIterator.HasNext() {
		queryResponse, err := resultsIterator.Next()
		if err != nil {
			return nil, fmt.Errorf("failed to read ledger result: %v", err)
		}

		var drug Drug

		if err := json.Unmarshal(queryResponse.Value, &drug); err != nil {
			return nil, fmt.Errorf(
				"failed to deserialize ledger record %s: %v",
				queryResponse.Key,
				err,
			)
		}

		drugs = append(drugs, &drug)
	}

	return drugs, nil
}

// VerifyDrug verifies the existence, QR hash, status, and expiry date of a drug.
func (s *SmartContract) VerifyDrug(
	ctx contractapi.TransactionContextInterface,
	drugID string,
	qrHash string,
) (*VerificationResult, error) {

	drug, err := s.ReadDrug(ctx, drugID)
	if err != nil {
		return &VerificationResult{
			DrugID:  drugID,
			IsValid: false,
			Status:  "NOT_FOUND",
			Message: err.Error(),
		}, nil
	}

	if drug.Status != "ACTIVE" {
		return &VerificationResult{
			DrugID:  drugID,
			IsValid: false,
			Status:  drug.Status,
			Message: "drug is not active",
		}, nil
	}

	if drug.QRHash != strings.TrimSpace(qrHash) {
		return &VerificationResult{
			DrugID:  drugID,
			IsValid: false,
			Status:  "QR_MISMATCH",
			Message: "QR hash does not match the blockchain record",
		}, nil
	}

	expiryDate, err := time.Parse("2006-01-02", drug.ExpiryDate)
	if err != nil {
		return nil, fmt.Errorf(
			"invalid expiry date stored for drug %s: %v",
			drugID,
			err,
		)
	}

	txTime, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return nil, fmt.Errorf("failed to obtain transaction timestamp: %v", err)
	}

	currentDate := time.Unix(txTime.Seconds, int64(txTime.Nanos)).UTC()

	if currentDate.After(expiryDate.Add(24*time.Hour - time.Nanosecond)) {
		return &VerificationResult{
			DrugID:  drugID,
			IsValid: false,
			Status:  "EXPIRED",
			Message: "drug has expired",
		}, nil
	}

	return &VerificationResult{
		DrugID:  drugID,
		IsValid: true,
		Status:  "GENUINE",
		Message: "drug record and QR hash are valid",
	}, nil
}

// TransferOwnership changes the current owner of a drug.
func (s *SmartContract) TransferOwnership(
	ctx contractapi.TransactionContextInterface,
	drugID string,
	newOwner string,
) error {

	drugID = strings.TrimSpace(drugID)
	newOwner = strings.TrimSpace(newOwner)

	if newOwner == "" {
		return fmt.Errorf("new owner cannot be empty")
	}

	drug, err := s.ReadDrug(ctx, drugID)
	if err != nil {
		return err
	}

	if drug.Status != "ACTIVE" {
		return fmt.Errorf(
			"ownership cannot be transferred because drug %s has status %s",
			drugID,
			drug.Status,
		)
	}

	if drug.CurrentOwner == newOwner {
		return fmt.Errorf(
			"new owner %s is already the current owner of drug %s",
			newOwner,
			drugID,
		)
	}

	txTime, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to obtain transaction timestamp: %v", err)
	}

	previousOwner := drug.CurrentOwner
	previousOwnershipHash := drug.OwnershipHash

	if previousOwnershipHash == "" {
		return fmt.Errorf(
			"ownership hash missing for drug %s",
			drugID,
		)
	}

	newOwnershipHash := computeOwnershipHash(
		previousOwnershipHash,
		drugID,
		previousOwner,
		newOwner,
	)

	drug.CurrentOwner = newOwner
	drug.OwnershipHash = newOwnershipHash
	drug.UpdatedAt = time.Unix(
		txTime.Seconds,
		int64(txTime.Nanos),
	).UTC().Format(time.RFC3339)

	drugJSON, err := json.Marshal(drug)
	if err != nil {
		return fmt.Errorf("failed to serialize drug record: %v", err)
	}

	return ctx.GetStub().PutState(drugID, drugJSON)
}

// RevokeDrug marks a drug as revoked.
func (s *SmartContract) RevokeDrug(
	ctx contractapi.TransactionContextInterface,
	drugID string,
	reason string,
) error {

	drugID = strings.TrimSpace(drugID)
	reason = strings.TrimSpace(reason)

	if reason == "" {
		return fmt.Errorf("revocation reason cannot be empty")
	}

	drug, err := s.ReadDrug(ctx, drugID)
	if err != nil {
		return err
	}

	if drug.Status == "REVOKED" {
		return fmt.Errorf("drug %s is already revoked", drugID)
	}

	txTime, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to obtain transaction timestamp: %v", err)
	}

	drug.Status = "REVOKED"
	drug.UpdatedAt = time.Unix(
		txTime.Seconds,
		int64(txTime.Nanos),
	).UTC().Format(time.RFC3339)

	drugJSON, err := json.Marshal(drug)
	if err != nil {
		return fmt.Errorf("failed to serialize revoked drug: %v", err)
	}

	if err := ctx.GetStub().PutState(drugID, drugJSON); err != nil {
		return fmt.Errorf("failed to revoke drug %s: %v", drugID, err)
	}

	return ctx.GetStub().SetEvent(
		"DrugRevoked",
		[]byte(fmt.Sprintf(
			`{"drugID":"%s","reason":"%s"}`,
			drugID,
			reason,
		)),
	)
}

// GetDrugHistory returns the complete modification history of a drug.
func (s *SmartContract) GetDrugHistory(
	ctx contractapi.TransactionContextInterface,
	drugID string,
) ([]*DrugHistory, error) {

	drugID = strings.TrimSpace(drugID)

	historyIterator, err := ctx.GetStub().GetHistoryForKey(drugID)
	if err != nil {
		return nil, fmt.Errorf(
			"failed to retrieve history for drug %s: %v",
			drugID,
			err,
		)
	}
	defer historyIterator.Close()

	var history []*DrugHistory

	for historyIterator.HasNext() {
		modification, err := historyIterator.Next()
		if err != nil {
			return nil, fmt.Errorf(
				"failed to read history entry for drug %s: %v",
				drugID,
				err,
			)
		}

		entry := &DrugHistory{
			TxID:      modification.TxId,
			IsDeleted: modification.IsDelete,
			Timestamp: time.Unix(
				modification.Timestamp.Seconds,
				int64(modification.Timestamp.Nanos),
			).UTC().Format(time.RFC3339),
		}

		if !modification.IsDelete && len(modification.Value) > 0 {
			var drug Drug

			if err := json.Unmarshal(modification.Value, &drug); err != nil {
				return nil, fmt.Errorf(
					"failed to deserialize history entry: %v",
					err,
				)
			}

			entry.Drug = &drug
		}

		history = append(history, entry)
	}

	return history, nil
}
