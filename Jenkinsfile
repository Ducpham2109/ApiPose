pipeline {
  agent any

  environment {
    IMAGE_NAME = 'api-adjust'
    IMAGE_TAG = "build-${env.BUILD_NUMBER}"
    IMAGE_LOCAL = "${IMAGE_NAME}:${IMAGE_TAG}"
    DATA_DIR = './data'
    STORAGE_ROOT = '/data/rrd'
    COMPOSE_FILE = 'jenkins/docker-compose.deploy.yml'
    COMPOSE_PROJECT = 'api-adjust'
    API_PORT = '8000'
  }

  options {
    skipDefaultCheckout(true)
    timestamps()
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Prepare environment file') {
      steps {
        script {
          if (!fileExists('.env')) {
            withCredentials([file(credentialsId: 'rerun-env', variable: 'ENV_FILE')]) {
              sh 'cp "$ENV_FILE" .env'
            }
          } else {
            echo '.env found in workspace; reusing.'
          }
        }
      }
    }

    stage('Build image') {
      steps {
        sh '''
          docker build --pull --tag ${IMAGE_LOCAL} .
          docker tag ${IMAGE_LOCAL} ${IMAGE_NAME}:latest
        '''
      }
    }

    stage('Smoke test image') {
      steps {
        sh '''
          rm -rf __tmp_rrd
          mkdir -p __tmp_rrd
          docker run --rm \
            --env-file .env \
            -e STORAGE_ROOT=/tmp/rrd \
            -v $WORKSPACE/__tmp_rrd:/tmp/rrd \
            ${IMAGE_LOCAL} \
            python -m compileall api_server.py label_odom2world_pose.py
        '''
      }
    }

    stage('Deploy') {
      steps {
        sh '''
          export API_ADJUST_IMAGE=${IMAGE_LOCAL}
          export DATA_DIR=${DATA_DIR}
          export STORAGE_ROOT=${STORAGE_ROOT}
          export API_PORT=${API_PORT}
          
          # Create directory for data storage
          mkdir -p ${DATA_DIR}/origin
          mkdir -p ${DATA_DIR}/process
          
          # Create jenkins directory (no need to copy .env)
          mkdir -p jenkins
          chmod 755 jenkins
          
          docker compose -p ${COMPOSE_PROJECT} -f ${COMPOSE_FILE} up -d --remove-orphans --force-recreate
        '''
      }
    }
  }

  post {
    always {
      sh 'rm -rf __tmp_rrd || true'
    }
    success {
      echo 'Deployment finished successfully.'
    }
    failure {
      sh 'docker logs api-adjust || true'
    }
  }
}
