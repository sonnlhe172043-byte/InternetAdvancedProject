// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FileStorage {

    struct File {
        string cid;
        address owner;      // backend signer (system controller)
        address uploader;   // user thật
        string filename;
        uint256 timestamp;
        bool isPublic;
    }

    uint256 public fileCount;

    mapping(uint256 => File) public files;

    // user => fileIds
    mapping(address => uint256[]) public userFiles;

    // fileId => user => permission
    mapping(uint256 => mapping(address => bool)) public canAccess;

    // =========================
    // EVENTS
    // =========================
    event FileUploaded(
        uint256 indexed id,
        string cid,
        address indexed uploader,
        string filename
    );

    event FileShared(
        uint256 indexed id,
        address indexed from,
        address indexed to
    );

    event PublicStateChanged(
        uint256 indexed id,
        bool isPublic
    );

    // =========================
    // UPLOAD FILE
    // =========================
    function uploadFile(
        string memory _cid,
        string memory _filename,
        address _uploader
    ) public {
        fileCount++;

        files[fileCount] = File({
            cid: _cid,
            owner: msg.sender,
            uploader: _uploader,
            filename: _filename,
            timestamp: block.timestamp,
            isPublic: false
        });

        userFiles[_uploader].push(fileCount);

        emit FileUploaded(fileCount, _cid, _uploader, _filename);
    }

    // =========================
    // SHARE FILE
    // =========================
    function shareFile(uint256 fileId, address user) public {
        require(files[fileId].owner == msg.sender, "Not owner");

        canAccess[fileId][user] = true;

        emit FileShared(fileId, msg.sender, user);
    }

    // =========================
    // REVOKE ACCESS
    // =========================
    function revokeAccess(uint256 fileId, address user) public {
        require(files[fileId].owner == msg.sender, "Not owner");

        canAccess[fileId][user] = false;
    }

    // =========================
    // SET PUBLIC / PRIVATE
    // =========================
    function setPublic(uint256 fileId, bool status) public {
        require(files[fileId].owner == msg.sender, "Not owner");

        files[fileId].isPublic = status;

        emit PublicStateChanged(fileId, status);
    }

    // =========================
    // CHECK ACCESS
    // =========================
    function canView(uint256 fileId, address user) public view returns (bool) {
        File memory f = files[fileId];

        return (
            f.isPublic ||
            f.owner == user ||
            f.uploader == user ||
            canAccess[fileId][user]
        );
    }

    // =========================
    // GET FILE
    // =========================
    function getFile(uint256 id) public view returns (File memory) {
        return files[id];
    }

    // =========================
    // GET USER FILES
    // =========================
    function getUserFiles(address user) public view returns (uint256[] memory) {
        return userFiles[user];
    }

    // =========================
    // GET TOTAL FILES
    // =========================
    function getTotalFiles() public view returns (uint256) {
        return fileCount;
    }

    // =========================
    // GET UPLOADER (OPTIONAL)
    // =========================
    function getUploader(uint256 id) public view returns (address) {
        return files[id].uploader;
    }
}