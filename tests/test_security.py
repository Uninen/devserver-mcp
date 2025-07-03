def test_api_prevents_path_traversal(test_app, auth_headers):
    """Test API prevents directory traversal attacks in project paths."""
    # Attempt path traversal
    traversal_attempts = [
        "../../../etc/passwd",
        "/home/user/../../../etc",
        "./../../sensitive",
    ]
    
    for malicious_path in traversal_attempts:
        response = test_app.post(
            "/api/projects/",
            json={
                "id": "malicious",
                "name": "Malicious Project",
                "path": malicious_path,
                "config_file": "devservers.yml"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400


def test_api_validates_absolute_paths(test_app, auth_headers):
    """Test API only accepts absolute paths for projects."""
    # Attempt relative paths
    relative_paths = [
        "relative/path",
        "./local",
        "projects/myapp",
    ]
    
    for relative_path in relative_paths:
        response = test_app.post(
            "/api/projects/",
            json={
                "id": "test",
                "name": "Test Project",
                "path": relative_path,
                "config_file": "devservers.yml"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400