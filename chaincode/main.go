package main

import (
	"fmt"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

func main() {
	drugChaincode, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		panic(fmt.Sprintf("failed to create pharmaceutical chaincode: %v", err))
	}

	if err := drugChaincode.Start(); err != nil {
		panic(fmt.Sprintf("failed to start pharmaceutical chaincode: %v", err))
	}
}
