.PHONY: test lint typecheck security audit ci build package clean

test:
	python -m pytest

lint:
	python -m ruff check src tests scripts

typecheck:
	python -m mypy src

security:
	python -m bandit -q -r src

audit:
	python -m pip_audit

ci: test lint typecheck security audit
	python scripts/verify_redteam_assets.py

build:
	sam build --template-file infra/template.yaml

package:
	zip -r maci-minimal-agent-control-infrastructure.zip . -x "*.pyc" "*/__pycache__/*" ".pytest_cache/*" ".aws-sam/*" ".git/*"

clean:
	rm -rf .pytest_cache .aws-sam maci-minimal-agent-control-infrastructure.zip
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

terraform-fmt:
	terraform -chdir=infra/terraform fmt -recursive

terraform-plan-dev:
	terraform -chdir=infra/terraform plan -var-file=environments/dev/terraform.tfvars

terraform-apply-dev:
	terraform -chdir=infra/terraform apply -var-file=environments/dev/terraform.tfvars

.PHONY: aws-lab aws-lab-check aws-lab-destroy

aws-lab-check:
	./quickstart/linux/00_check_prereqs.sh

aws-lab:
	./quickstart/linux/dev_first_deploy.sh

aws-lab-destroy:
	./quickstart/linux/99_destroy_dev.sh
