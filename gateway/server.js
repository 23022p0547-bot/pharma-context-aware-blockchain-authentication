'use strict';

const express = require('express');
const grpc = require('@grpc/grpc-js');
const {
    connect,
    hash,
    signers,
} = require('@hyperledger/fabric-gateway');

const crypto = require('crypto');
const fs = require('fs/promises');
const path = require('path');

const app = express();
app.use(express.json());

const channelName = 'mychannel';
const chaincodeName = 'pharma';
const mspId = 'Org1MSP';

const testNetworkPath = path.resolve(
    __dirname,
    '../../test-network'
);

const cryptoPath = path.join(
    testNetworkPath,
    'organizations',
    'peerOrganizations',
    'org1.example.com'
);

const certDirectoryPath = path.join(
    cryptoPath,
    'users',
    'User1@org1.example.com',
    'msp',
    'signcerts'
);

const keyDirectoryPath = path.join(
    cryptoPath,
    'users',
    'User1@org1.example.com',
    'msp',
    'keystore'
);

const tlsCertPath = path.join(
    cryptoPath,
    'peers',
    'peer0.org1.example.com',
    'tls',
    'ca.crt'
);

const peerEndpoint = 'localhost:7051';
const peerHostAlias = 'peer0.org1.example.com';

async function newGrpcConnection() {
    const tlsRootCert = await fs.readFile(tlsCertPath);

    const tlsCredentials =
        grpc.credentials.createSsl(tlsRootCert);

    return new grpc.Client(
        peerEndpoint,
        tlsCredentials,
        {
            'grpc.ssl_target_name_override': peerHostAlias,
        }
    );
}

async function newIdentity() {
    const files = await fs.readdir(certDirectoryPath);

    const certificateFile = files.find(
        (file) => file.endsWith('.pem')
    );

    if (!certificateFile) {
        throw new Error(
            `No identity certificate found in ${certDirectoryPath}`
        );
    }

    const credentials = await fs.readFile(
        path.join(certDirectoryPath, certificateFile)
    );

    return {
        mspId,
        credentials,
    };
}

async function newSigner() {
    const files = await fs.readdir(keyDirectoryPath);
    const privateKeyPem = await fs.readFile(
        path.join(keyDirectoryPath, files[0])
    );

    const privateKey =
        crypto.createPrivateKey(privateKeyPem);

    return signers.newPrivateKeySigner(privateKey);
}

async function getContract() {
    const client = await newGrpcConnection();
    const identity = await newIdentity();
    const signer = await newSigner();

    const gateway = connect({
        client,
        identity,
        signer,
        hash: hash.sha256,
        evaluateOptions: () => ({
            deadline: Date.now() + 5000,
        }),
        endorseOptions: () => ({
            deadline: Date.now() + 15000,
        }),
        submitOptions: () => ({
            deadline: Date.now() + 5000,
        }),
        commitStatusOptions: () => ({
            deadline: Date.now() + 60000,
        }),
    });

    const network = gateway.getNetwork(channelName);
    const contract = network.getContract(chaincodeName);

    return {
        contract,
        gateway,
        client,
    };
}

function decodeResult(resultBytes) {
    const text = Buffer.from(resultBytes).toString('utf8');

    if (!text) {
        return {};
    }

    try {
        return JSON.parse(text);
    } catch {
        return text;
    }
}

app.get('/health', async (req, res) => {
    res.json({
        status: 'UP',
        service: 'Pharma Fabric Gateway',
    });
});

app.get('/drugs', async (req, res) => {
    let resources;

    try {
        resources = await getContract();

        const result =
            await resources.contract.evaluateTransaction(
                'GetAllDrugs'
            );

        res.json(decodeResult(result));
    } catch (error) {
        console.error(error);
        res.status(500).json({
            error: error.message,
        });
    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});

app.get('/drugs/:drugId', async (req, res) => {
    let resources;

    try {
        resources = await getContract();

        const result =
            await resources.contract.evaluateTransaction(
                'ReadDrug',
                req.params.drugId
            );

        res.json(decodeResult(result));
    } catch (error) {
        console.error(error);
        res.status(500).json({
            error: error.message,
        });
    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});

app.get('/drugs/:drugId/history', async (req, res) => {
    let resources;

    try {
        resources = await getContract();

        const result =
            await resources.contract.evaluateTransaction(
                'GetDrugHistory',
                req.params.drugId
            );

        res.json(decodeResult(result));
    } catch (error) {
        console.error(error);
        res.status(500).json({
            error: error.message,
        });
    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});

app.post('/verify', async (req, res) => {
    const { drugId, qrHash } = req.body;

    if (!drugId || !qrHash) {
        return res.status(400).json({
            error: 'drugId and qrHash are required',
        });
    }

    let resources;

    try {
        resources = await getContract();

        const result =
            await resources.contract.evaluateTransaction(
                'VerifyDrug',
                drugId,
                qrHash
            );

        res.json(decodeResult(result));
    } catch (error) {
        console.error(error);
        res.status(500).json({
            error: error.message,
        });
    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});

const port = 3000;
app.post("/drugs", async (req, res) => {
    let client;
    let gateway;

    try {
        const {
            drugID,
            drugName,
            manufacturer,
            batchNumber,
            manufactureDate,
            expiryDate,
            qrHash
        } = req.body;

        if (
            !drugID ||
            !drugName ||
            !manufacturer ||
            !batchNumber ||
            !manufactureDate ||
            !expiryDate ||
            !qrHash
        ) {
            return res.status(400).json({
                success: false,
                message: "All drug-registration fields are required"
            });
        }

        client = await newGrpcConnection();

        gateway = connect({
            client,
            identity: await newIdentity(),
            signer: await newSigner(),
            hash: hash.sha256,
            evaluateOptions: () => ({
                deadline: Date.now() + 5000
            }),
            endorseOptions: () => ({
                deadline: Date.now() + 15000
            }),
            submitOptions: () => ({
                deadline: Date.now() + 5000
            }),
            commitStatusOptions: () => ({
                deadline: Date.now() + 60000
            })
        });

        const network = gateway.getNetwork(channelName);
        const contract = network.getContract(chaincodeName);

        await contract.submitTransaction(
                "RegisterDrug",
                drugID,
                drugName,
                manufacturer,
                batchNumber,
                manufactureDate,
                expiryDate,
                manufacturer,      // Initial Current Owner
                qrHash
        );

        res.status(201).json({
            success: true,
            message: "Drug registered successfully on the blockchain",
            drugID
        });

    } catch (error) {
        console.error("RegisterDrug error:", error);

        const message =
            error?.details?.[0]?.message ||
            error?.message ||
            "Blockchain registration failed";

        const duplicate =
            message.toLowerCase().includes("already exists");

        res.status(duplicate ? 409 : 500).json({
            success: false,
            message
        });

    } finally {
        if (gateway) {
            gateway.close();
        }

        if (client) {
            client.close();
        }
    }
});

app.get("/drugs/:drugId/history", async (req, res) => {
    try {
        const { drugId } = req.params;

        if (!drugId) {
            return res.status(400).json({
                error: "drugId is required"
            });
        }

        const result = await contract.evaluateTransaction(
            "GetDrugHistory",
            drugId
        );

        const resultText = result.toString();

        let history;

        try {
            history = JSON.parse(resultText);
        } catch (parseError) {
            history = resultText;
        }

        return res.status(200).json({
            drugId: drugId,
            history: history
        });

    } catch (error) {
        console.error("History retrieval error:", error);

        return res.status(500).json({
            error: error.message
        });
    }
});

app.post('/drugs/:drugId/transfer', async (req, res) => {
    const drugId = req.params.drugId;
    const { newOwner } = req.body;

    if (!drugId || !newOwner || newOwner.trim() === '') {
        return res.status(400).json({
            success: false,
            error: 'drugId and newOwner are required',
        });
    }

    let resources;

    try {
        resources = await getContract();

        await resources.contract.submitTransaction(
            'TransferOwnership',
            drugId,
            newOwner.trim()
        );

        const result =
            await resources.contract.evaluateTransaction(
                'ReadDrug',
                drugId
            );

        const updatedDrug = decodeResult(result);

        return res.status(200).json({
            success: true,
            message: 'Ownership transferred successfully',
            drug: updatedDrug,
        });

    } catch (error) {
        console.error('Ownership transfer error:', error);

        return res.status(500).json({
            success: false,
            error: error.message,
        });

    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});

app.post('/drugs/:drugId/revoke', async (req, res) => {
    const drugId = req.params.drugId;
    const reason = req.body.reason;

    if (!drugId || !reason || reason.trim() === '') {
        return res.status(400).json({
            success: false,
            error: 'drugId and revocation reason are required',
        });
    }

    let resources;

    try {
        resources = await getContract();

        await resources.contract.submitTransaction(
            'RevokeDrug',
            drugId,
            reason.trim()
        );

        const result =
            await resources.contract.evaluateTransaction(
                'ReadDrug',
                drugId
            );

        return res.status(200).json({
            success: true,
            message: 'Drug revoked successfully',
            reason: reason.trim(),
            drug: decodeResult(result),
        });

    } catch (error) {
        console.error('Drug revocation error:', error);

        const message = error?.message || 'Drug revocation failed';

        const statusCode =
            message.toLowerCase().includes('already revoked')
                ? 409
                : 500;

        return res.status(statusCode).json({
            success: false,
            error: message,
        });

    } finally {
        resources?.gateway.close();
        resources?.client.close();
    }
});
app.listen(port, () => {
    console.log(
        `Pharma Fabric Gateway running at http://localhost:${port}`
    );
});

