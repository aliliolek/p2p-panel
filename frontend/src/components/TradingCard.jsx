import PropTypes from "prop-types";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Typography,
} from "@mui/material";
import { getSideColor } from "../utils/trading";
import { formatNumber } from "../utils/formatters";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";

function DetailRow({ icon, label, value }) {
  const renderValue =
    typeof value === "string" ? (
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, fontSize: 13, textAlign: "right" }}
      >
        {value || "-"}
      </Typography>
    ) : (
      value
    );
  return (
    <Stack
      direction="row"
      spacing={1}
      alignItems="center"
      justifyContent="space-between"
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
        {icon ? (
          <Box
            sx={{
              width: 20,
              display: "flex",
              justifyContent: "center",
              color: "text.secondary",
            }}
          >
            {icon}
          </Box>
        ) : null}
        {label ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontSize: 13, whiteSpace: "nowrap" }}
          >
            {label}
          </Typography>
        ) : null}
      </Box>
      <Box
        sx={{ display: "flex", alignItems: "center", gap: 1, flexShrink: 0 }}
      >
        {renderValue}
      </Box>
    </Stack>
  );
}

DetailRow.propTypes = {
  icon: PropTypes.node,
  label: PropTypes.string,
  value: PropTypes.node,
};

const formatPrimaryLine = (value, suffix = "") => {
  const formatted = formatNumber(value, 6);
  if (formatted === "-") return "-";
  return `${formatted}${suffix ? ` ${suffix}` : ""}`;
};

function TradingCard({
  typeLabel,
  entityId,
  side,
  token,
  fiatCurrency,
  price,
  cryptoAmount,
  fiatAmount,
  statusLabel,
  statusColor = "default",
  detailRows = [],
  footer,
  highlight = false,
  actions = null,
  cornerActions = null,
  dimmed = false,
}) {
  const cryptoText = formatPrimaryLine(cryptoAmount, token);
  const fiatText =
    formatNumber(fiatAmount) + (fiatCurrency ? ` ${fiatCurrency}` : "");
  const priceText = formatNumber(price, 6);
  const totalText = fiatText.trim() || "-";

  const sideColorKey = getSideColor(side);
  const priceChipLabel = `${priceText}`.trim();

  const renderConversion = () => {
    const isSell = String(side || "").toUpperCase() === "SELL";
    const left = isSell ? cryptoText : totalText;
    const right = isSell ? totalText : cryptoText;
    const op = isSell ? "×" : "÷";
    return (
      <Stack
        direction="row"
        alignItems="center"
        spacing={0.75}
        sx={{ mt: 0.5 }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {left}
        </Typography>
        <ArrowForwardIosIcon
          fontSize="inherit"
          sx={{ fontSize: 14, color: "text.secondary" }}
        />
        <Chip
          size="small"
          label={`${op} ${priceChipLabel}`}
          variant="outlined"
          sx={{ fontWeight: 600 }}
        />
        <ArrowForwardIosIcon
          fontSize="inherit"
          sx={{ fontSize: 14, color: "text.secondary" }}
        />
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {right}
        </Typography>
      </Stack>
    );
  };

  return (
    <Card
      variant={highlight ? "outlined" : "elevation"}
      sx={{
        borderColor: highlight ? "success.light" : "divider",
        backgroundColor: (theme) =>
          highlight
            ? theme.palette.success?.lighter || theme.palette.success.light
            : theme.palette.background.paper,
        position: "relative",
        opacity: dimmed ? 0.25 : 1,
        transition: "opacity 0.2s ease",
      }}
    >
      {cornerActions ? (
        <Box
          sx={{
            position: "absolute",
            top: 4,
            right: 4,
            display: "flex",
            gap: 0.5,
          }}
        >
          {cornerActions}
        </Box>
      ) : null}
      <CardContent sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
        >
          <Stack spacing={0.3}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              <Box
                component="span"
                sx={{
                  color: (theme) =>
                    sideColorKey !== "default"
                      ? theme.palette[sideColorKey]?.main ||
                        theme.palette.text.primary
                      : theme.palette.text.primary,
                }}
              >
                {side || "-"}
              </Box>{" "}
              {token || "-"}
              <Typography variant="caption" color="text.secondary" noWrap>
                {` - ${fiatCurrency || ""}`}
              </Typography>
            </Typography>

            <Typography variant="caption" color="text.secondary"></Typography>
          </Stack>
        </Stack>

        {renderConversion()}

        {detailRows.length ? (
          <>
            <Divider sx={{ my: 1 }} />
            <Stack spacing={1.2}>
              {detailRows.map((row) => (
                <DetailRow
                  key={row.key || row.label || row.value}
                  icon={row.icon}
                  label={row.label}
                  value={row.value}
                />
              ))}
            </Stack>
          </>
        ) : null}

        {actions ? (
          <Box sx={{ mt: 1 }}>
            <Divider sx={{ mb: 1 }} />
            {actions}
          </Box>
        ) : null}

        {footer ? (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
            {footer}
            <Typography variant="overline" color="text.secondary">
              {` -  ${entityId || "-"}`}
            </Typography>
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}

TradingCard.propTypes = {
  typeLabel: PropTypes.string.isRequired,
  entityId: PropTypes.string,
  side: PropTypes.string,
  token: PropTypes.string,
  fiatCurrency: PropTypes.string,
  price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  cryptoAmount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  fiatAmount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  statusLabel: PropTypes.string,
  statusColor: PropTypes.string,
  detailRows: PropTypes.arrayOf(
    PropTypes.shape({
      icon: PropTypes.node,
      label: PropTypes.string,
      value: PropTypes.node,
    })
  ),
  footer: PropTypes.string,
  highlight: PropTypes.bool,
  actions: PropTypes.node,
  cornerActions: PropTypes.node,
  dimmed: PropTypes.bool,
};

TradingCard.defaultProps = {
  entityId: "",
  side: "",
  token: "",
  fiatCurrency: "",
  price: undefined,
  cryptoAmount: undefined,
  fiatAmount: undefined,
  statusLabel: "",
  statusColor: "default",
  detailRows: [],
  footer: "",
  highlight: false,
  actions: null,
  cornerActions: null,
  dimmed: false,
};

export default TradingCard;
