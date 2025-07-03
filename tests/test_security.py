def test_api_rejects_project_registration_with_path_traversal_attempts(test_app, auth_headers):
    """Test that the API prevents directory traversal attacks when registering projects."""
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
        
        assert response.status_code == 404


def test_api_rejects_project_registration_with_relative_paths(test_app, auth_headers):
    """Test that the API only accepts absolute paths for project registration."""
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
        
        assert response.status_code == 404