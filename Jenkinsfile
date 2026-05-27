pipeline {
    agent any

    environment {
        PYTHON = 'python3'
        VENV_DIR = 'venv'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup') {
            steps {
                sh '''
                    ${PYTHON} -m venv ${VENV_DIR}
                    . ${VENV_DIR}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    pytest --junitxml=test-results.xml --cov=app --cov-report=xml:coverage.xml --cov-report=html:htmlcov
                '''
            }
        }

        stage('Build Tailwind') {
            steps {
                sh '''
                    if [ -f tailwindcss ]; then
                        ./tailwindcss -i app/static/css/tailwind-input.css -o app/static/css/tailwind.min.css --minify
                    fi
                '''
            }
        }

        stage('Build Release') {
            steps {
                sh '''
                    . ${VENV_DIR}/bin/activate
                    ${PYTHON} build_release.py
                '''
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            environment {
                DEPLOY_HOST = credentials('deploy-host')
                DEPLOY_PATH = credentials('deploy-path')
                DEPLOY_USER = credentials('deploy-user')
            }
            steps {
                sh '''
                    scp -r release_build/* ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/
                    ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd ${DEPLOY_PATH} && supervisorctl restart portal"
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'test-results.xml'
            publishHTML(target: [
                allowMissing: true,
                alwaysLinkToLastBuild: false,
                keepAll: true,
                reportDir: 'htmlcov',
                reportFiles: 'index.html',
                reportName: 'Coverage Report'
            ])
            cleanWs()
        }
        success {
            echo 'Build and deploy completed.'
        }
        failure {
            echo 'Build failed.'
        }
    }
}
